/* SPDX-License-Identifier: GPL-2.0 */
/*
 * DIANA-OS — P2P Component Bus (Header)
 *
 * Author: Sahidh — DIANA Architecture
 */

#ifndef _DIANA_P2P_BUS_H
#define _DIANA_P2P_BUS_H

#include <linux/types.h>
#include <linux/spinlock.h>
#include <linux/list.h>
#include <linux/ktime.h>
#include <linux/seq_file.h>
#include "synapse_chip.h"

#define P2P_MAX_COMPONENTS      4
#define P2P_LOG_MAX             100
#define P2P_NAME_LEN            16

/* Message types */
#define MSG_PREFETCH_REQUEST    0
#define MSG_DATA_READY          1
#define MSG_ACK                 2
#define MSG_SYNC                3

static const char * const p2p_msg_type_str[] = {
    "PREFETCH_REQUEST",
    "DATA_READY",
    "ACK",
    "SYNC",
};

struct diana_component;

struct p2p_message {
    char sender[P2P_NAME_LEN];
    char receiver[P2P_NAME_LEN];
    uint8_t msg_type;
    uint64_t payload;
    ktime_t timestamp;
    struct list_head list;
};

/* Callback for receiving P2P messages */
typedef void (*p2p_receive_fn)(struct diana_component *comp,
                               struct p2p_message *msg);

struct diana_component {
    char name[P2P_NAME_LEN];
    struct synapse_chip synapse;
    p2p_receive_fn receive_callback;
    uint64_t events_handled;
    uint64_t p2p_sent;
    uint64_t p2p_received;
    void *private_data;
};

struct p2p_bus {
    spinlock_t lock;
    struct list_head message_log;
    uint64_t message_count;
    uint32_t log_size;
    struct diana_component *registry[P2P_MAX_COMPONENTS];
    int registry_count;
};

/* Bus lifecycle */
void p2p_bus_init(struct p2p_bus *bus);
void p2p_bus_destroy(struct p2p_bus *bus);

/* Component registration — rejects "CPU" */
int p2p_register(struct p2p_bus *bus, struct diana_component *comp);

/* Send a message to a specific receiver */
int p2p_send(struct p2p_bus *bus, const char *sender,
             const char *receiver, uint8_t msg_type, uint64_t payload);

/* Broadcast to all except sender and CPU */
int p2p_broadcast(struct p2p_bus *bus, const char *sender,
                  uint8_t msg_type, uint64_t payload);

/* Stats */
uint64_t p2p_get_message_count(struct p2p_bus *bus);

/* Dump log to /proc/diana/p2p_log */
void p2p_log_to_proc(struct p2p_bus *bus, struct seq_file *m);

#endif /* _DIANA_P2P_BUS_H */
