/* SPDX-License-Identifier: GPL-2.0 */
/*
 * DIANA-OS — P2P Component Bus Implementation
 *
 * Thread-safe message passing between SYNAPSE components.
 * CPU is deliberately excluded from the registry.
 *
 * Author: Sahidh — DIANA Architecture
 */

#include <linux/kernel.h>
#include <linux/slab.h>
#include <linux/string.h>
#include "p2p_bus.h"

void p2p_bus_init(struct p2p_bus *bus)
{
    spin_lock_init(&bus->lock);
    INIT_LIST_HEAD(&bus->message_log);
    bus->message_count = 0;
    bus->log_size = 0;
    bus->registry_count = 0;
    memset(bus->registry, 0, sizeof(bus->registry));
}

void p2p_bus_destroy(struct p2p_bus *bus)
{
    struct p2p_message *msg, *tmp;
    unsigned long flags;

    spin_lock_irqsave(&bus->lock, flags);

    list_for_each_entry_safe(msg, tmp, &bus->message_log, list) {
        list_del(&msg->list);
        kfree(msg);
    }

    bus->log_size = 0;
    bus->message_count = 0;

    spin_unlock_irqrestore(&bus->lock, flags);
}

int p2p_register(struct p2p_bus *bus, struct diana_component *comp)
{
    unsigned long flags;

    /* REJECT CPU — CPU is never allowed on the P2P bus */
    if (strncasecmp(comp->name, "CPU", 3) == 0) {
        pr_err("DIANA P2P: REJECTED registration of '%s' — "
               "CPU is NEVER allowed on P2P bus!\n", comp->name);
        return -EACCES;
    }

    spin_lock_irqsave(&bus->lock, flags);

    if (bus->registry_count >= P2P_MAX_COMPONENTS) {
        spin_unlock_irqrestore(&bus->lock, flags);
        pr_err("DIANA P2P: registry full, cannot register '%s'\n",
               comp->name);
        return -ENOSPC;
    }

    bus->registry[bus->registry_count++] = comp;

    spin_unlock_irqrestore(&bus->lock, flags);

    pr_info("DIANA P2P: registered component '%s' [%d/%d]\n",
            comp->name, bus->registry_count, P2P_MAX_COMPONENTS);

    return 0;
}

/* Internal: find component by name */
static struct diana_component *p2p_find_component(struct p2p_bus *bus,
                                                   const char *name)
{
    int i;

    for (i = 0; i < bus->registry_count; i++) {
        if (bus->registry[i] &&
            strncmp(bus->registry[i]->name, name, P2P_NAME_LEN) == 0)
            return bus->registry[i];
    }

    return NULL;
}

/* Internal: add message to log, enforce max size */
static void p2p_log_message(struct p2p_bus *bus, const char *sender,
                            const char *receiver, uint8_t msg_type,
                            uint64_t payload)
{
    struct p2p_message *msg;

    msg = kmalloc(sizeof(*msg), GFP_ATOMIC);
    if (!msg)
        return;

    strscpy(msg->sender, sender, P2P_NAME_LEN);
    strscpy(msg->receiver, receiver, P2P_NAME_LEN);
    msg->msg_type = msg_type;
    msg->payload = payload;
    msg->timestamp = ktime_get();

    list_add_tail(&msg->list, &bus->message_log);
    bus->log_size++;

    /* Trim old messages if over limit */
    while (bus->log_size > P2P_LOG_MAX) {
        struct p2p_message *old;

        old = list_first_entry(&bus->message_log,
                               struct p2p_message, list);
        list_del(&old->list);
        kfree(old);
        bus->log_size--;
    }
}

int p2p_send(struct p2p_bus *bus, const char *sender,
             const char *receiver, uint8_t msg_type, uint64_t payload)
{
    struct diana_component *target;
    struct p2p_message delivery;
    unsigned long flags;

    /* Never deliver to CPU */
    if (strncasecmp(receiver, "CPU", 3) == 0) {
        pr_warn("DIANA P2P: blocked message to CPU from '%s'\n", sender);
        return -EACCES;
    }

    spin_lock_irqsave(&bus->lock, flags);

    target = p2p_find_component(bus, receiver);
    if (!target) {
        spin_unlock_irqrestore(&bus->lock, flags);
        return -ENODEV;
    }

    /* Log the message */
    p2p_log_message(bus, sender, receiver, msg_type, payload);
    bus->message_count++;

    /* Build delivery message */
    strscpy(delivery.sender, sender, P2P_NAME_LEN);
    strscpy(delivery.receiver, receiver, P2P_NAME_LEN);
    delivery.msg_type = msg_type;
    delivery.payload = payload;
    delivery.timestamp = ktime_get();

    target->p2p_received++;

    spin_unlock_irqrestore(&bus->lock, flags);

    /* Deliver to receiver callback (outside lock to avoid deadlock) */
    if (target->receive_callback)
        target->receive_callback(target, &delivery);

    return 0;
}

int p2p_broadcast(struct p2p_bus *bus, const char *sender,
                  uint8_t msg_type, uint64_t payload)
{
    struct p2p_message delivery;
    unsigned long flags;
    int i, delivered = 0;

    spin_lock_irqsave(&bus->lock, flags);

    for (i = 0; i < bus->registry_count; i++) {
        struct diana_component *comp = bus->registry[i];

        if (!comp)
            continue;

        /* Skip sender */
        if (strncmp(comp->name, sender, P2P_NAME_LEN) == 0)
            continue;

        /* NEVER deliver to CPU */
        if (strncasecmp(comp->name, "CPU", 3) == 0)
            continue;

        p2p_log_message(bus, sender, comp->name, msg_type, payload);
        bus->message_count++;
        comp->p2p_received++;
        delivered++;
    }

    /* Build delivery template */
    strscpy(delivery.sender, sender, P2P_NAME_LEN);
    delivery.msg_type = msg_type;
    delivery.payload = payload;
    delivery.timestamp = ktime_get();

    spin_unlock_irqrestore(&bus->lock, flags);

    /* Deliver callbacks outside the lock */
    for (i = 0; i < bus->registry_count; i++) {
        struct diana_component *comp = bus->registry[i];

        if (!comp)
            continue;
        if (strncmp(comp->name, sender, P2P_NAME_LEN) == 0)
            continue;
        if (strncasecmp(comp->name, "CPU", 3) == 0)
            continue;

        if (comp->receive_callback) {
            strscpy(delivery.receiver, comp->name, P2P_NAME_LEN);
            comp->receive_callback(comp, &delivery);
        }
    }

    return delivered;
}

uint64_t p2p_get_message_count(struct p2p_bus *bus)
{
    unsigned long flags;
    uint64_t count;

    spin_lock_irqsave(&bus->lock, flags);
    count = bus->message_count;
    spin_unlock_irqrestore(&bus->lock, flags);

    return count;
}

void p2p_log_to_proc(struct p2p_bus *bus, struct seq_file *m)
{
    struct p2p_message *msg;
    unsigned long flags;

    seq_puts(m, "=== DIANA P2P Bus Message Log ===\n");
    seq_printf(m, "Total messages: %llu\n\n", bus->message_count);
    seq_puts(m, "TIMESTAMP            SENDER    -> RECEIVER   TYPE               PAYLOAD\n");
    seq_puts(m, "-------------------------------------------------------------------\n");

    spin_lock_irqsave(&bus->lock, flags);

    list_for_each_entry(msg, &bus->message_log, list) {
        const char *type_str = "UNKNOWN";
        s64 ns = ktime_to_ns(msg->timestamp);

        if (msg->msg_type < ARRAY_SIZE(p2p_msg_type_str))
            type_str = p2p_msg_type_str[msg->msg_type];

        seq_printf(m, "%-20lld %-8s -> %-10s %-18s 0x%016llx\n",
                   ns, msg->sender, msg->receiver,
                   type_str, msg->payload);
    }

    spin_unlock_irqrestore(&bus->lock, flags);
}
