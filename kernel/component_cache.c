/* SPDX-License-Identifier: GPL-2.0 */
/*
 * DIANA-OS — Cache SYNAPSE Component
 *
 * Handles: cache hit/miss, inode cache events
 * Predicts: what to keep in cache vs evict
 * P2P: tells RAM to evict/keep, tells SSD to re-read
 *
 * Author: Sahidh — DIANA Architecture
 */

#include <linux/kernel.h>
#include <linux/string.h>
#include <linux/seq_file.h>
#include "p2p_bus.h"
#include "cpu_observer.h"

/* Event IDs for CACHE */
#define CACHE_EVT_HIT           0
#define CACHE_EVT_MISS          1
#define CACHE_EVT_EVICTION      2
#define CACHE_EVT_INODE_LOOKUP  3
#define CACHE_EVT_INODE_CREATE  4
#define CACHE_EVT_INODE_EVICT   5
#define CACHE_EVT_DENTRY_LOOKUP 6
#define CACHE_EVT_PAGE_HIT      7
#define CACHE_EVT_PAGE_MISS     8
#define CACHE_EVT_PREFETCH_HIT  9
#define CACHE_EVT_PREFETCH_MISS 10

struct cache_component {
    struct diana_component base;
    struct p2p_bus *bus;
    struct cpu_observer *cpu;

    /* Cache-specific state */
    uint64_t cache_hits;
    uint64_t cache_misses;
    uint64_t evictions;
    uint64_t inode_lookups;
    uint64_t prefetch_hits;
    uint64_t prefetch_misses;
};

static void cache_receive_p2p(struct diana_component *comp,
                              struct p2p_message *msg)
{
    struct cache_component *cache = container_of(comp,
                                    struct cache_component, base);

    switch (msg->msg_type) {
    case MSG_PREFETCH_REQUEST:
        /* RAM or SSD wants something cached */
        synapse_observe(&comp->synapse, CACHE_EVT_INODE_CREATE);
        cache->inode_lookups++;
        /* Acknowledge the request */
        p2p_send(cache->bus, "CACHE", msg->sender,
                 MSG_ACK, msg->payload);
        cache->base.p2p_sent++;
        break;
    case MSG_SYNC:
        /* RAM reports page fault pattern */
        synapse_observe(&comp->synapse, CACHE_EVT_PAGE_MISS);
        break;
    case MSG_DATA_READY:
        synapse_observe(&comp->synapse, CACHE_EVT_PREFETCH_HIT);
        cache->prefetch_hits++;
        break;
    default:
        break;
    }

    if (cache->cpu) {
        char status[CPU_STATUS_LEN];

        snprintf(status, sizeof(status),
                 "P2P from %s: type=%u payload=0x%llx",
                 msg->sender, msg->msg_type, msg->payload);
        cpu_receive_status(cache->cpu, "CACHE", status);
    }
}

void component_cache_init(struct cache_component *cache,
                          struct p2p_bus *bus,
                          struct cpu_observer *cpu)
{
    memset(cache, 0, sizeof(*cache));
    strscpy(cache->base.name, "CACHE", P2P_NAME_LEN);
    synapse_init(&cache->base.synapse, "CACHE");
    cache->base.receive_callback = cache_receive_p2p;
    cache->bus = bus;
    cache->cpu = cpu;

    p2p_register(bus, &cache->base);

    pr_info("DIANA CACHE: SYNAPSE intelligence initialized\n");
}

void component_cache_handle_event(struct cache_component *cache,
                                   bool hit)
{
    uint32_t confidence;
    uint8_t predicted;

    if (hit) {
        synapse_observe(&cache->base.synapse, CACHE_EVT_HIT);
        cache->cache_hits++;
    } else {
        synapse_observe(&cache->base.synapse, CACHE_EVT_MISS);
        cache->cache_misses++;
    }
    cache->base.events_handled++;

    /* Predict next cache event */
    predicted = synapse_predict(&cache->base.synapse, &confidence);

    if (confidence > 700) {
        if (predicted == CACHE_EVT_MISS ||
            predicted == CACHE_EVT_PAGE_MISS) {
            /* Predict a miss coming — tell SSD to re-read */
            p2p_send(cache->bus, "CACHE", "SSD",
                     MSG_PREFETCH_REQUEST,
                     cache->cache_misses);
            cache->base.p2p_sent++;
        }
        if (predicted == CACHE_EVT_EVICTION) {
            /* Predict eviction — tell RAM to keep region */
            p2p_send(cache->bus, "CACHE", "RAM",
                     MSG_SYNC, 0);
            cache->base.p2p_sent++;
        }
    }

    if (cache->cpu) {
        char status[CPU_STATUS_LEN];

        snprintf(status, sizeof(status),
                 "cache %s (hits: %llu, misses: %llu, ratio: %llu%%)",
                 hit ? "HIT" : "MISS",
                 cache->cache_hits, cache->cache_misses,
                 (cache->cache_hits + cache->cache_misses) > 0 ?
                  (cache->cache_hits * 100) /
                  (cache->cache_hits + cache->cache_misses) : 0);
        cpu_receive_status(cache->cpu, "CACHE", status);
    }
}

void component_cache_handle_inode(struct cache_component *cache,
                                   bool lookup)
{
    if (lookup) {
        synapse_observe(&cache->base.synapse, CACHE_EVT_INODE_LOOKUP);
        cache->inode_lookups++;
    } else {
        synapse_observe(&cache->base.synapse, CACHE_EVT_INODE_EVICT);
        cache->evictions++;
    }
    cache->base.events_handled++;
}

void component_cache_get_stats(struct cache_component *cache,
                                struct seq_file *m)
{
    uint64_t total = cache->cache_hits + cache->cache_misses;

    seq_puts(m, "[CACHE SYNAPSE]\n");
    seq_printf(m, "  patterns_learned: %llu\n",
               cache->base.synapse.patterns_learned);
    seq_printf(m, "  predictions: %llu\n",
               cache->base.synapse.predictions_made);
    seq_printf(m, "  accuracy: %u%%\n",
               synapse_get_accuracy(&cache->base.synapse));
    seq_printf(m, "  cache_hits: %llu\n", cache->cache_hits);
    seq_printf(m, "  cache_misses: %llu\n", cache->cache_misses);
    seq_printf(m, "  hit_ratio: %llu%%\n",
               total > 0 ? (cache->cache_hits * 100) / total : 0);
    seq_printf(m, "  evictions: %llu\n", cache->evictions);
    seq_printf(m, "  inode_lookups: %llu\n", cache->inode_lookups);
    seq_printf(m, "  prefetch_hits: %llu / misses: %llu\n",
               cache->prefetch_hits, cache->prefetch_misses);
    seq_printf(m, "  p2p_sent: %llu / received: %llu\n",
               cache->base.p2p_sent, cache->base.p2p_received);
    seq_puts(m, "\n");
}
