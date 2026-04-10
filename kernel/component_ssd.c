/* SPDX-License-Identifier: GPL-2.0 */
/*
 * DIANA-OS — SSD SYNAPSE Component
 *
 * Handles: VFS read/write, file open/close
 * Predicts: next files user will access
 * P2P: tells RAM data is ready, tells CACHE to cache inodes
 *
 * Author: Sahidh — DIANA Architecture
 */

#include <linux/kernel.h>
#include <linux/string.h>
#include <linux/seq_file.h>
#include "p2p_bus.h"
#include "cpu_observer.h"

/* Event IDs for SSD */
#define SSD_EVT_READ_SMALL      0   /* < 4KB */
#define SSD_EVT_READ_MED        1   /* 4KB - 1MB */
#define SSD_EVT_READ_LARGE      2   /* > 1MB */
#define SSD_EVT_WRITE_SMALL     3
#define SSD_EVT_WRITE_MED       4
#define SSD_EVT_WRITE_LARGE     5
#define SSD_EVT_OPEN            6
#define SSD_EVT_CLOSE           7
#define SSD_EVT_SEEK            8
#define SSD_EVT_PREFETCH_HIT    9
#define SSD_EVT_PREFETCH_MISS   10
#define SSD_EVT_SEQUENTIAL      11
#define SSD_EVT_RANDOM          12

struct ssd_component {
    struct diana_component base;
    struct p2p_bus *bus;
    struct cpu_observer *cpu;

    /* SSD-specific state */
    uint64_t total_reads;
    uint64_t total_writes;
    uint64_t bytes_read;
    uint64_t bytes_written;
    uint64_t files_opened;
    uint64_t prefetch_hits;
    uint64_t prefetch_misses;
    char last_file[128];
};

static void ssd_receive_p2p(struct diana_component *comp,
                            struct p2p_message *msg)
{
    struct ssd_component *ssd = container_of(comp, struct ssd_component,
                                              base);

    switch (msg->msg_type) {
    case MSG_PREFETCH_REQUEST:
        /* RAM or GPU wants data pre-loaded from SSD */
        synapse_observe(&comp->synapse, SSD_EVT_READ_MED);
        ssd->total_reads++;

        /* Acknowledge and signal data ready */
        p2p_send(ssd->bus, "SSD", msg->sender,
                 MSG_DATA_READY, msg->payload);
        ssd->base.p2p_sent++;
        break;
    case MSG_ACK:
        ssd->prefetch_hits++;
        synapse_observe(&comp->synapse, SSD_EVT_PREFETCH_HIT);
        break;
    default:
        break;
    }

    if (ssd->cpu) {
        char status[CPU_STATUS_LEN];

        snprintf(status, sizeof(status),
                 "P2P from %s: type=%u payload=0x%llx",
                 msg->sender, msg->msg_type, msg->payload);
        cpu_receive_status(ssd->cpu, "SSD", status);
    }
}

void component_ssd_init(struct ssd_component *ssd,
                        struct p2p_bus *bus,
                        struct cpu_observer *cpu)
{
    memset(ssd, 0, sizeof(*ssd));
    strscpy(ssd->base.name, "SSD", P2P_NAME_LEN);
    synapse_init(&ssd->base.synapse, "SSD");
    ssd->base.receive_callback = ssd_receive_p2p;
    ssd->bus = bus;
    ssd->cpu = cpu;

    p2p_register(bus, &ssd->base);

    pr_info("DIANA SSD: SYNAPSE intelligence initialized\n");
}

void component_ssd_handle_read(struct ssd_component *ssd,
                                const char *filename, size_t size,
                                const char *comm)
{
    uint8_t event_id;
    uint32_t confidence;
    uint8_t predicted;

    ssd->total_reads++;
    ssd->bytes_read += size;
    strscpy(ssd->last_file, filename, sizeof(ssd->last_file));

    /* Classify read size */
    if (size < 4096)
        event_id = SSD_EVT_READ_SMALL;
    else if (size < 1048576)
        event_id = SSD_EVT_READ_MED;
    else
        event_id = SSD_EVT_READ_LARGE;

    synapse_observe(&ssd->base.synapse, event_id);
    ssd->base.events_handled++;

    /* Predict next I/O event */
    predicted = synapse_predict(&ssd->base.synapse, &confidence);

    if (confidence > 700) {
        if (predicted == SSD_EVT_READ_LARGE ||
            predicted == SSD_EVT_READ_MED) {
            /* Tell RAM that file data is about to arrive */
            p2p_send(ssd->bus, "SSD", "RAM",
                     MSG_DATA_READY, size);
            ssd->base.p2p_sent++;
        }
        if (predicted == SSD_EVT_SEQUENTIAL) {
            /* Tell CACHE to cache these inodes */
            p2p_send(ssd->bus, "SSD", "CACHE",
                     MSG_PREFETCH_REQUEST, size);
            ssd->base.p2p_sent++;
        }
    }

    if (ssd->cpu) {
        char status[CPU_STATUS_LEN];

        snprintf(status, sizeof(status),
                 "read %zu bytes from %s by %s",
                 size, filename, comm);
        cpu_receive_status(ssd->cpu, "SSD", status);
    }
}

void component_ssd_handle_write(struct ssd_component *ssd,
                                 const char *filename, size_t size)
{
    uint8_t event_id;

    ssd->total_writes++;
    ssd->bytes_written += size;

    if (size < 4096)
        event_id = SSD_EVT_WRITE_SMALL;
    else if (size < 1048576)
        event_id = SSD_EVT_WRITE_MED;
    else
        event_id = SSD_EVT_WRITE_LARGE;

    synapse_observe(&ssd->base.synapse, event_id);
    ssd->base.events_handled++;
}

void component_ssd_handle_open(struct ssd_component *ssd,
                                const char *filename)
{
    ssd->files_opened++;
    synapse_observe(&ssd->base.synapse, SSD_EVT_OPEN);
    ssd->base.events_handled++;
    strscpy(ssd->last_file, filename, sizeof(ssd->last_file));
}

void component_ssd_get_stats(struct ssd_component *ssd, struct seq_file *m)
{
    seq_puts(m, "[SSD SYNAPSE]\n");
    seq_printf(m, "  patterns_learned: %llu\n",
               ssd->base.synapse.patterns_learned);
    seq_printf(m, "  predictions: %llu\n",
               ssd->base.synapse.predictions_made);
    seq_printf(m, "  accuracy: %u%%\n",
               synapse_get_accuracy(&ssd->base.synapse));
    seq_printf(m, "  total_reads: %llu (%llu bytes)\n",
               ssd->total_reads, ssd->bytes_read);
    seq_printf(m, "  total_writes: %llu (%llu bytes)\n",
               ssd->total_writes, ssd->bytes_written);
    seq_printf(m, "  files_opened: %llu\n", ssd->files_opened);
    seq_printf(m, "  prefetch_hits: %llu / misses: %llu\n",
               ssd->prefetch_hits, ssd->prefetch_misses);
    seq_printf(m, "  p2p_sent: %llu / received: %llu\n",
               ssd->base.p2p_sent, ssd->base.p2p_received);
    seq_printf(m, "  last_file: %s\n", ssd->last_file);
    seq_puts(m, "\n");
}

void component_ssd_execute(struct ssd_component *ssd, const char *event_name, uint32_t confidence)
{
    if (confidence < 800)
        return;

    if (strncasecmp(event_name, "read_large", 10) == 0 || 
        strncasecmp(event_name, "sequential", 10) == 0) {
        
        /* Autonomously trigger an asynchronous background read/prefetch into 
         * the kernel page cache. We simulate the block preparation here. */
        if (ssd->cpu) {
            ssd->cpu->commands_issued++;
            cpu_receive_status(ssd->cpu, "SSD", "EXECUTED: Async Block Prefetch");
        }
    }
}
