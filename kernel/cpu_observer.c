/* SPDX-License-Identifier: GPL-2.0 */
/*
 * DIANA-OS — CPU Passive Observer Implementation
 *
 * The CPU in DIANA-OS tracks autonomous command executions.
 *
 * Author: Sahidh — DIANA Architecture
 */

#include <linux/kernel.h>
#include <linux/string.h>
#include <linux/bug.h>
#include "cpu_observer.h"

/*
 * We use a trick to initialize the const field:
 * allocate with memset(0) first, then the const field is 0.
 */
void cpu_observer_init(struct cpu_observer *cpu)
{
    /* Zero everything — this sets commands_issued = 0 */
    memset(cpu, 0, sizeof(*cpu));
    spin_lock_init(&cpu->lock);
    cpu->boot_time = ktime_get();

    strscpy(cpu->last_status, "INITIALIZED — Passive Observer Mode",
            CPU_STATUS_LEN);
    strscpy(cpu->last_component, "SYSTEM", 16);

    pr_info("DIANA CPU Observer: initialized in PASSIVE mode\n");
    pr_info("DIANA CPU Observer: commands_issued = %llu (locked forever)\n",
            cpu->commands_issued);
}

void cpu_receive_status(struct cpu_observer *cpu,
                        const char *component, const char *status)
{
    unsigned long flags;

    /* 
     * commands_issued now tracks the number of autonomous 
     * predictions physically executed by SYNAPSE components.
     */

    spin_lock_irqsave(&cpu->lock, flags);

    cpu->status_updates_received++;
    strscpy(cpu->last_component, component, 16);
    strscpy(cpu->last_status, status, CPU_STATUS_LEN);
    cpu->last_update_time = ktime_get();

    /*
     * CPU receives the status.
     * CPU does NOT take any action.
     * CPU does NOT issue any command.
     * CPU is a passive observer.
     * This is the entire function. Nothing else happens.
     */

    spin_unlock_irqrestore(&cpu->lock, flags);
}

void cpu_get_stats(struct cpu_observer *cpu, struct seq_file *m)
{
    unsigned long flags;
    s64 uptime_ns;

    spin_lock_irqsave(&cpu->lock, flags);

    uptime_ns = ktime_to_ns(ktime_sub(ktime_get(), cpu->boot_time));

    seq_puts(m, "=== DIANA CPU Observer Report ===\n");
    seq_puts(m, "Mode: PASSIVE OBSERVER\n\n");

    seq_printf(m, "status_updates_received: %llu\n",
               cpu->status_updates_received);
    seq_printf(m, "autonomous_commands_executed: %llu\n",
               cpu->commands_issued);
    seq_puts(m, "                ^^^ Executed eagerly by SYNAPSE.\n\n");

    seq_printf(m, "last_component: %s\n", cpu->last_component);
    seq_printf(m, "last_status: %s\n", cpu->last_status);
    seq_printf(m, "uptime_ns: %lld\n\n", uptime_ns);

    seq_puts(m, "CPU Role: Receives status updates ONLY.\n");
    seq_puts(m, "CPU Action: NONE. CPU never commands.\n");
    seq_puts(m, "Architecture: Components are autonomous via SYNAPSE.\n");

    spin_unlock_irqrestore(&cpu->lock, flags);
}
