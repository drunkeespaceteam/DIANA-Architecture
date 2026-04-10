/* SPDX-License-Identifier: GPL-2.0 */
/*
 * DIANA-OS — CPU Passive Observer (Header)
 *
 * Author: Sahidh — DIANA Architecture
 */

#ifndef _DIANA_CPU_OBSERVER_H
#define _DIANA_CPU_OBSERVER_H

#include <linux/types.h>
#include <linux/spinlock.h>
#include <linux/ktime.h>
#include <linux/seq_file.h>

#define CPU_STATUS_LEN  256

struct cpu_observer {
    spinlock_t lock;
    uint64_t status_updates_received;
    uint64_t commands_issued;  /* Track autonomous commands executed by SYNAPSE */
    char last_status[CPU_STATUS_LEN];
    char last_component[16];
    ktime_t last_update_time;
    ktime_t boot_time;
};

/* Initialize the CPU observer — commands_issued locked at 0 */
void cpu_observer_init(struct cpu_observer *cpu);

/*
 * Receive a status update from a component.
 * CPU ONLY observes — it does NOT issue any command.
 */
void cpu_receive_status(struct cpu_observer *cpu,
                        const char *component, const char *status);

/* Write stats to /proc/diana/cpu_report */
void cpu_get_stats(struct cpu_observer *cpu, struct seq_file *m);

#endif /* _DIANA_CPU_OBSERVER_H */
