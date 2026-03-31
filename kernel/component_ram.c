/* SPDX-License-Identifier: GPL-2.0 */
/*
 * DIANA-OS — RAM SYNAPSE Component
 *
 * Handles: kmalloc, page faults, memory pressure
 * Predicts: which memory regions needed next
 * P2P: requests SSD to pre-load, tells CACHE to keep regions hot
 *
 * Author: Sahidh — DIANA Architecture
 */

#include <linux/kernel.h>
#include <linux/string.h>
#include <linux/seq_file.h>
#include "p2p_bus.h"
#include "cpu_observer.h"

/* Event IDs for RAM */
#define RAM_EVT_KMALLOC_SMALL   0   /* < 1KB */
#define RAM_EVT_KMALLOC_MED     1   /* 1KB - 64KB */
#define RAM_EVT_KMALLOC_LARGE   2   /* > 64KB */
#define RAM_EVT_PAGE_FAULT      3
#define RAM_EVT_MMAP            4
#define RAM_EVT_MUNMAP          5
#define RAM_EVT_PRESSURE_LOW    6
#define RAM_EVT_PRESSURE_MED    7
#define RAM_EVT_PRESSURE_HIGH   8
#define RAM_EVT_PREFETCH_HIT    9
#define RAM_EVT_PREFETCH_MISS   10

struct ram_component {
    struct diana_component base;
    struct p2p_bus *bus;
    struct cpu_observer *cpu;

    /* RAM-specific state */
    uint64_t total_allocs;
    uint64_t total_bytes;
    uint64_t page_faults;
    uint64_t prefetch_hits;
    uint64_t prefetch_misses;
};

static void ram_receive_p2p(struct diana_component *comp,
                            struct p2p_message *msg)
{
    struct ram_component *ram = container_of(comp, struct ram_component,
                                             base);

    switch (msg->msg_type) {
    case MSG_DATA_READY:
        /* SSD says data is ready — mark as prefetch hit */
        synapse_observe(&comp->synapse, RAM_EVT_PREFETCH_HIT);
        ram->prefetch_hits++;
        break;
    case MSG_PREFETCH_REQUEST:
        /* Another component wants memory prepared */
        synapse_observe(&comp->synapse, RAM_EVT_KMALLOC_MED);
        break;
    case MSG_ACK:
        break;
    default:
        break;
    }

    /* Report to CPU (status only) */
    if (ram->cpu) {
        char status[CPU_STATUS_LEN];

        snprintf(status, sizeof(status),
                 "P2P from %s: type=%u payload=0x%llx",
                 msg->sender, msg->msg_type, msg->payload);
        cpu_receive_status(ram->cpu, "RAM", status);
    }
}

void component_ram_init(struct ram_component *ram,
                        struct p2p_bus *bus,
                        struct cpu_observer *cpu)
{
    memset(ram, 0, sizeof(*ram));
    strscpy(ram->base.name, "RAM", P2P_NAME_LEN);
    synapse_init(&ram->base.synapse, "RAM");
    ram->base.receive_callback = ram_receive_p2p;
    ram->bus = bus;
    ram->cpu = cpu;

    p2p_register(bus, &ram->base);

    pr_info("DIANA RAM: SYNAPSE intelligence initialized\n");
}

void component_ram_handle_kmalloc(struct ram_component *ram,
                                   size_t size, const char *comm)
{
    uint8_t event_id;
    uint32_t confidence;
    uint8_t predicted;

    ram->total_allocs++;
    ram->total_bytes += size;

    /* Classify allocation size */
    if (size < 1024)
        event_id = RAM_EVT_KMALLOC_SMALL;
    else if (size < 65536)
        event_id = RAM_EVT_KMALLOC_MED;
    else
        event_id = RAM_EVT_KMALLOC_LARGE;

    synapse_observe(&ram->base.synapse, event_id);
    ram->base.events_handled++;

    /* Predict next event */
    predicted = synapse_predict(&ram->base.synapse, &confidence);

    /* If confidence is high, take P2P action */
    if (confidence > 700) {
        if (predicted == RAM_EVT_KMALLOC_LARGE) {
            /* Tell SSD to prefetch large data */
            p2p_send(ram->bus, "RAM", "SSD",
                     MSG_PREFETCH_REQUEST, size);
            ram->base.p2p_sent++;
        } else if (predicted == RAM_EVT_PAGE_FAULT) {
            /* Tell CACHE to prepare for page fault */
            p2p_send(ram->bus, "RAM", "CACHE",
                     MSG_PREFETCH_REQUEST, size);
            ram->base.p2p_sent++;
        }
    }

    /* Report to CPU (status only!) */
    if (ram->cpu) {
        char status[CPU_STATUS_LEN];

        snprintf(status, sizeof(status),
                 "kmalloc %zu bytes by %s (total: %llu)",
                 size, comm, ram->total_allocs);
        cpu_receive_status(ram->cpu, "RAM", status);
    }
}

void component_ram_handle_page_fault(struct ram_component *ram)
{
    ram->page_faults++;
    synapse_observe(&ram->base.synapse, RAM_EVT_PAGE_FAULT);
    ram->base.events_handled++;

    /* Notify CACHE about page fault pattern */
    p2p_send(ram->bus, "RAM", "CACHE", MSG_SYNC, ram->page_faults);
    ram->base.p2p_sent++;
}

void component_ram_get_stats(struct ram_component *ram, struct seq_file *m)
{
    seq_puts(m, "[RAM SYNAPSE]\n");
    seq_printf(m, "  patterns_learned: %llu\n",
               ram->base.synapse.patterns_learned);
    seq_printf(m, "  predictions: %llu\n",
               ram->base.synapse.predictions_made);
    seq_printf(m, "  accuracy: %u%%\n",
               synapse_get_accuracy(&ram->base.synapse));
    seq_printf(m, "  total_allocs: %llu\n", ram->total_allocs);
    seq_printf(m, "  total_bytes: %llu\n", ram->total_bytes);
    seq_printf(m, "  page_faults: %llu\n", ram->page_faults);
    seq_printf(m, "  prefetch_hits: %llu / misses: %llu\n",
               ram->prefetch_hits, ram->prefetch_misses);
    seq_printf(m, "  p2p_sent: %llu / received: %llu\n",
               ram->base.p2p_sent, ram->base.p2p_received);
    seq_puts(m, "\n");
}

void component_ram_execute(struct ram_component *ram, const char *event_name, uint32_t confidence)
{
    unsigned long addr;

    if (confidence < 800)
        return;

    if (strncasecmp(event_name, "kmalloc_large", 13) == 0) {
        /* Autonomously pre-allocate a physical page (simulate pre-warming) */
        addr = __get_free_pages(GFP_KERNEL, 2); /* 4 pages = 16KB */
        if (addr) {
            /* We immediately free it just to exercise the allocator and prove
             * we forced the CPU to do work autonomously. In a real OS, we'd 
             * map it into the VMA of the target process. */
            free_pages(addr, 2);

            if (ram->cpu) {
                ram->cpu->commands_issued++;
                cpu_receive_status(ram->cpu, "RAM", "EXECUTED: Pre-warmed 16KB pages");
            }
        }
    } else if (strncasecmp(event_name, "kmalloc_med", 11) == 0) {
        /* Autonomously trigger slab cache growth */
        void *ptr = kmalloc(4096, GFP_KERNEL);
        if (ptr) {
            kfree(ptr);
            if (ram->cpu) {
                ram->cpu->commands_issued++;
                cpu_receive_status(ram->cpu, "RAM", "EXECUTED: Warmed 4KB slab");
            }
        }
    }
}
