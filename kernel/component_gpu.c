/* SPDX-License-Identifier: GPL-2.0 */
/*
 * DIANA-OS — GPU SYNAPSE Component
 *
 * Handles: DRM/DRI events, GPU-heavy process switches
 * Predicts: next render requirements
 * P2P: tells RAM to prepare buffers, tells SSD to load textures
 *
 * Author: Sahidh — DIANA Architecture
 */

#include <linux/kernel.h>
#include <linux/string.h>
#include <linux/seq_file.h>
#include "p2p_bus.h"
#include "cpu_observer.h"

/* Event IDs for GPU */
#define GPU_EVT_PROCESS_SWITCH  0
#define GPU_EVT_RENDER_START    1
#define GPU_EVT_RENDER_END      2
#define GPU_EVT_BUFFER_ALLOC    3
#define GPU_EVT_TEXTURE_LOAD    4
#define GPU_EVT_SHADER_COMPILE  5
#define GPU_EVT_VSYNC           6
#define GPU_EVT_COMPUTE_START   7
#define GPU_EVT_COMPUTE_END     8
#define GPU_EVT_PREFETCH_HIT    9
#define GPU_EVT_PREFETCH_MISS   10

struct gpu_component {
    struct diana_component base;
    struct p2p_bus *bus;
    struct cpu_observer *cpu;

    /* GPU-specific state */
    uint64_t render_count;
    uint64_t compute_count;
    uint64_t buffer_allocs;
    uint64_t texture_loads;
    uint64_t prefetch_hits;
    uint64_t prefetch_misses;
    char last_gpu_process[64];
};

static void gpu_receive_p2p(struct diana_component *comp,
                            struct p2p_message *msg)
{
    struct gpu_component *gpu = container_of(comp, struct gpu_component,
                                              base);

    switch (msg->msg_type) {
    case MSG_DATA_READY:
        /* RAM/SSD have data ready for GPU */
        synapse_observe(&comp->synapse, GPU_EVT_PREFETCH_HIT);
        gpu->prefetch_hits++;
        break;
    case MSG_PREFETCH_REQUEST:
        /* Component wants GPU to prepare something */
        synapse_observe(&comp->synapse, GPU_EVT_BUFFER_ALLOC);
        break;
    case MSG_ACK:
        break;
    default:
        break;
    }

    if (gpu->cpu) {
        char status[CPU_STATUS_LEN];

        snprintf(status, sizeof(status),
                 "P2P from %s: type=%u payload=0x%llx",
                 msg->sender, msg->msg_type, msg->payload);
        cpu_receive_status(gpu->cpu, "GPU", status);
    }
}

void component_gpu_init(struct gpu_component *gpu,
                        struct p2p_bus *bus,
                        struct cpu_observer *cpu)
{
    memset(gpu, 0, sizeof(*gpu));
    strscpy(gpu->base.name, "GPU", P2P_NAME_LEN);
    synapse_init(&gpu->base.synapse, "GPU");
    gpu->base.receive_callback = gpu_receive_p2p;
    gpu->bus = bus;
    gpu->cpu = cpu;

    p2p_register(bus, &gpu->base);

    pr_info("DIANA GPU: SYNAPSE intelligence initialized\n");
}

void component_gpu_handle_process(struct gpu_component *gpu,
                                   const char *comm, pid_t pid)
{
    uint32_t confidence;
    uint8_t predicted;

    synapse_observe(&gpu->base.synapse, GPU_EVT_PROCESS_SWITCH);
    gpu->base.events_handled++;
    strscpy(gpu->last_gpu_process, comm, sizeof(gpu->last_gpu_process));

    /* Predict what GPU will need next */
    predicted = synapse_predict(&gpu->base.synapse, &confidence);

    if (confidence > 700) {
        if (predicted == GPU_EVT_RENDER_START ||
            predicted == GPU_EVT_BUFFER_ALLOC) {
            /* Tell RAM to prepare render buffers */
            p2p_send(gpu->bus, "GPU", "RAM",
                     MSG_PREFETCH_REQUEST, (uint64_t)pid);
            gpu->base.p2p_sent++;
        }
        if (predicted == GPU_EVT_TEXTURE_LOAD) {
            /* Tell SSD to load texture assets */
            p2p_send(gpu->bus, "GPU", "SSD",
                     MSG_PREFETCH_REQUEST, (uint64_t)pid);
            gpu->base.p2p_sent++;
        }
    }

    if (gpu->cpu) {
        char status[CPU_STATUS_LEN];

        snprintf(status, sizeof(status),
                 "GPU-relevant process: %s (pid %d)", comm, pid);
        cpu_receive_status(gpu->cpu, "GPU", status);
    }
}

void component_gpu_handle_render(struct gpu_component *gpu, bool start)
{
    if (start) {
        synapse_observe(&gpu->base.synapse, GPU_EVT_RENDER_START);
        gpu->render_count++;
    } else {
        synapse_observe(&gpu->base.synapse, GPU_EVT_RENDER_END);
    }
    gpu->base.events_handled++;
}

void component_gpu_get_stats(struct gpu_component *gpu, struct seq_file *m)
{
    seq_puts(m, "[GPU SYNAPSE]\n");
    seq_printf(m, "  patterns_learned: %llu\n",
               gpu->base.synapse.patterns_learned);
    seq_printf(m, "  predictions: %llu\n",
               gpu->base.synapse.predictions_made);
    seq_printf(m, "  accuracy: %u%%\n",
               synapse_get_accuracy(&gpu->base.synapse));
    seq_printf(m, "  render_count: %llu\n", gpu->render_count);
    seq_printf(m, "  compute_count: %llu\n", gpu->compute_count);
    seq_printf(m, "  buffer_allocs: %llu\n", gpu->buffer_allocs);
    seq_printf(m, "  texture_loads: %llu\n", gpu->texture_loads);
    seq_printf(m, "  prefetch_hits: %llu / misses: %llu\n",
               gpu->prefetch_hits, gpu->prefetch_misses);
    seq_printf(m, "  p2p_sent: %llu / received: %llu\n",
               gpu->base.p2p_sent, gpu->base.p2p_received);
    seq_printf(m, "  last_process: %s\n", gpu->last_gpu_process);
    seq_puts(m, "\n");
}
