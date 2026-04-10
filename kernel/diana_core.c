/* SPDX-License-Identifier: GPL-2.0 */
/*
 * DIANA-Nexus Kernel v1.0
 *
 * The heart of DIANA-OS. A real Linux kernel module that intercepts
 * kernel operations via kprobes and routes them through SYNAPSE
 * component intelligence.
 *
 * Intercepts:
 *   - Memory allocation (kmalloc/vmalloc)
 *   - File system access (VFS hooks)
 *   - Process scheduling events
 *
 * Architecture:
 *   - Each hardware component has its own SYNAPSE chip
 *   - Components communicate via P2P bus
 *   - CPU is a passive observer — never commands
 *   - Userspace LSTM sends hints via /proc/diana/hints
 *
 * Author: Sahidh — DIANA Architecture
 * License: GPL v2
 */

#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/init.h>
#include <linux/proc_fs.h>
#include <linux/seq_file.h>
#include <linux/slab.h>
#include <linux/kprobes.h>
#include <linux/spinlock.h>
#include <linux/list.h>
#include <linux/timer.h>
#include <linux/workqueue.h>
#include <linux/mm.h>
#include <linux/fs.h>
#include <linux/dcache.h>
#include <linux/uaccess.h>
#include <linux/sched.h>
#include <linux/version.h>

#include "synapse_chip.h"
#include "p2p_bus.h"
#include "cpu_observer.h"

MODULE_LICENSE("GPL");
MODULE_AUTHOR("Sahidh — DIANA Architecture");
MODULE_DESCRIPTION("DIANA-Nexus Kernel v1.0 — "
                   "Distributed Intelligent Autonomous Neural Architecture");
MODULE_VERSION("1.0");

/* ================================================================
 * Forward declarations for component types
 * ================================================================ */

/* RAM component (from component_ram.c) */
struct ram_component {
    struct diana_component base;
    struct p2p_bus *bus;
    struct cpu_observer *cpu;
    uint64_t total_allocs;
    uint64_t total_bytes;
    uint64_t page_faults;
    uint64_t prefetch_hits;
    uint64_t prefetch_misses;
};
extern void component_ram_init(struct ram_component *, struct p2p_bus *,
                               struct cpu_observer *);
extern void component_ram_handle_kmalloc(struct ram_component *,
                                          size_t, const char *);
extern void component_ram_get_stats(struct ram_component *, struct seq_file *);
extern void component_ram_execute(struct ram_component *, const char *, uint32_t);

/* GPU component (from component_gpu.c) */
struct gpu_component {
    struct diana_component base;
    struct p2p_bus *bus;
    struct cpu_observer *cpu;
    uint64_t render_count;
    uint64_t compute_count;
    uint64_t buffer_allocs;
    uint64_t texture_loads;
    uint64_t prefetch_hits;
    uint64_t prefetch_misses;
    char last_gpu_process[64];
};
extern void component_gpu_init(struct gpu_component *, struct p2p_bus *,
                               struct cpu_observer *);
extern void component_gpu_handle_process(struct gpu_component *,
                                          const char *, pid_t);
extern void component_gpu_get_stats(struct gpu_component *, struct seq_file *);

/* SSD component (from component_ssd.c) */
struct ssd_component {
    struct diana_component base;
    struct p2p_bus *bus;
    struct cpu_observer *cpu;
    uint64_t total_reads;
    uint64_t total_writes;
    uint64_t bytes_read;
    uint64_t bytes_written;
    uint64_t files_opened;
    uint64_t prefetch_hits;
    uint64_t prefetch_misses;
    char last_file[128];
};
extern void component_ssd_init(struct ssd_component *, struct p2p_bus *,
                               struct cpu_observer *);
extern void component_ssd_handle_read(struct ssd_component *,
                                       const char *, size_t, const char *);
extern void component_ssd_get_stats(struct ssd_component *, struct seq_file *);
extern void component_ssd_execute(struct ssd_component *, const char *, uint32_t);

/* Cache component (from component_cache.c) */
struct cache_component {
    struct diana_component base;
    struct p2p_bus *bus;
    struct cpu_observer *cpu;
    uint64_t cache_hits;
    uint64_t cache_misses;
    uint64_t evictions;
    uint64_t inode_lookups;
    uint64_t prefetch_hits;
    uint64_t prefetch_misses;
};
extern void component_cache_init(struct cache_component *, struct p2p_bus *,
                                 struct cpu_observer *);
extern void component_cache_handle_event(struct cache_component *, bool);
extern void component_cache_get_stats(struct cache_component *,
                                       struct seq_file *);

/* ================================================================
 * Global DIANA state
 * ================================================================ */

static struct p2p_bus         diana_bus;
static struct cpu_observer    diana_cpu;
static struct ram_component   diana_ram;
static struct gpu_component   diana_gpu;
static struct ssd_component   diana_ssd;
static struct cache_component diana_cache;

static struct proc_dir_entry *proc_diana_dir;
static struct proc_dir_entry *proc_stats;
static struct proc_dir_entry *proc_hints;
static struct proc_dir_entry *proc_p2p_log;
static struct proc_dir_entry *proc_cpu_report;

/* Hints buffer for userspace LSTM writes */
#define HINTS_BUF_SIZE 4096
static char hints_buffer[HINTS_BUF_SIZE];
static DEFINE_SPINLOCK(hints_lock);

/* Event counter for throttling */
static atomic64_t event_counter = ATOMIC64_INIT(0);
#define EVENT_SAMPLE_RATE 100  /* Process every Nth event to reduce overhead */

/* ================================================================
 * kprobe handlers — intercept real kernel operations
 * ================================================================ */

/*
 * kprobe: __kmalloc
 * Intercepts every kernel memory allocation.
 */
static struct kprobe kp_kmalloc = {
    .symbol_name = "__kmalloc",
};

static int __kprobes kmalloc_pre_handler(struct kprobe *p,
                                          struct pt_regs *regs)
{
    size_t size;
    uint64_t count;

    count = atomic64_inc_return(&event_counter);
    if (count % EVENT_SAMPLE_RATE != 0)
        return 0;

    /* x86_64: first argument is in RDI register */
#ifdef CONFIG_X86_64
    size = (size_t)regs->di;
#else
    size = 0;  /* Architecture-specific — extend as needed */
#endif

    component_ram_handle_kmalloc(&diana_ram, size, current->comm);

    return 0;
}

/*
 * kprobe: vfs_read
 * Intercepts every file read in the kernel.
 */
static struct kprobe kp_vfs_read = {
    .symbol_name = "vfs_read",
};

static int __kprobes vfs_read_pre_handler(struct kprobe *p,
                                           struct pt_regs *regs)
{
    struct file *file;
    const char *filename = "unknown";
    size_t count_val;
    uint64_t count;

    count = atomic64_inc_return(&event_counter);
    if (count % EVENT_SAMPLE_RATE != 0)
        return 0;

#ifdef CONFIG_X86_64
    file = (struct file *)regs->di;
    count_val = (size_t)regs->dx;
#else
    return 0;
#endif

    if (file && file->f_path.dentry)
        filename = file->f_path.dentry->d_name.name;

    component_ssd_handle_read(&diana_ssd, filename, count_val,
                              current->comm);

    return 0;
}

/*
 * kprobe: finish_task_switch (scheduler)
 * Intercepts every process context switch.
 */
static struct kprobe kp_schedule = {
    .symbol_name = "finish_task_switch.isra.0",
};

static int __kprobes schedule_pre_handler(struct kprobe *p,
                                           struct pt_regs *regs)
{
    uint64_t count;

    count = atomic64_inc_return(&event_counter);
    if (count % EVENT_SAMPLE_RATE != 0)
        return 0;

    /* Notify GPU about process switches (GPU-relevant detection) */
    component_gpu_handle_process(&diana_gpu, current->comm,
                                 current->pid);

    /* Notify CACHE about scheduling event (cache pressure indicator) */
    component_cache_handle_event(&diana_cache, true);

    return 0;
}

/* ================================================================
 * /proc/diana/ filesystem handlers
 * ================================================================ */

/*
 * /proc/diana/stats — per-component statistics
 */
static int diana_stats_show(struct seq_file *m, void *v)
{
    seq_puts(m, "╔═══════════════════════════════════════════╗\n");
    seq_puts(m, "║    DIANA-OS — SYNAPSE Chip Statistics     ║\n");
    seq_puts(m, "╚═══════════════════════════════════════════╝\n\n");

    component_ram_get_stats(&diana_ram, m);
    component_gpu_get_stats(&diana_gpu, m);
    component_ssd_get_stats(&diana_ssd, m);
    component_cache_get_stats(&diana_cache, m);

    seq_puts(m, "[P2P BUS]\n");
    seq_printf(m, "  total_messages: %llu\n",
               p2p_get_message_count(&diana_bus));
    seq_puts(m, "\n");

    seq_puts(m, "[CPU OBSERVER]\n");
    seq_printf(m, "  status_updates_received: %llu\n",
               diana_cpu.status_updates_received);
    seq_printf(m, "  commands_issued: %llu\n",
               diana_cpu.commands_issued);  /* ALWAYS 0 */
    seq_puts(m, "\n");

    return 0;
}

static int diana_stats_open(struct inode *inode, struct file *file)
{
    return single_open(file, diana_stats_show, NULL);
}

static const struct proc_ops diana_stats_ops = {
    .proc_open    = diana_stats_open,
    .proc_read    = seq_read,
    .proc_lseek   = seq_lseek,
    .proc_release = single_release,
};

/*
 * /proc/diana/hints — userspace LSTM writes predictions here
 * Format: "COMPONENT:EVENT:CONFIDENCE\n"
 * Example: "RAM:browser_data:0.89\n"
 */
static ssize_t diana_hints_write(struct file *file, const char __user *buf,
                                  size_t count, loff_t *ppos)
{
    char kbuf[256];
    char component[16], event[64];
    int confidence_int;
    size_t len;
    unsigned long flags;

    len = min(count, sizeof(kbuf) - 1);
    if (copy_from_user(kbuf, buf, len))
        return -EFAULT;
    kbuf[len] = '\0';

    /* Parse: "COMPONENT:EVENT:CONFIDENCE\n" */
    if (sscanf(kbuf, "%15[^:]:%63[^:]:%d", component, event,
               &confidence_int) != 3) {
        pr_warn("DIANA hints: invalid format: %s\n", kbuf);
        return -EINVAL;
    }

    /* Convert confidence from 0.XX to 0-1000 scale */
    /* Input might be 0.89 parsed as 0, or 89, or 890 */
    if (confidence_int < 0)
        confidence_int = 0;
    if (confidence_int > 1000)
        confidence_int = 1000;

    pr_debug("DIANA hint: %s:%s:%d\n", component, event, confidence_int);

    /* Route hint to appropriate component SYNAPSE */
    if (strncasecmp(component, "RAM", 3) == 0) {
        synapse_apply_hint(&diana_ram.base.synapse, 0,
                           (uint32_t)confidence_int);
        component_ram_execute(&diana_ram, event, (uint32_t)confidence_int);
    } else if (strncasecmp(component, "GPU", 3) == 0) {
        synapse_apply_hint(&diana_gpu.base.synapse, 0,
                           (uint32_t)confidence_int);
    } else if (strncasecmp(component, "SSD", 3) == 0) {
        synapse_apply_hint(&diana_ssd.base.synapse, 0,
                           (uint32_t)confidence_int);
        component_ssd_execute(&diana_ssd, event, (uint32_t)confidence_int);
    } else if (strncasecmp(component, "CACHE", 5) == 0) {
        synapse_apply_hint(&diana_cache.base.synapse, 0,
                           (uint32_t)confidence_int);
    }

    /* Store in hints buffer */
    spin_lock_irqsave(&hints_lock, flags);
    snprintf(hints_buffer, HINTS_BUF_SIZE, "%s", kbuf);
    spin_unlock_irqrestore(&hints_lock, flags);

    return count;
}

static int diana_hints_show(struct seq_file *m, void *v)
{
    unsigned long flags;

    seq_puts(m, "=== DIANA Hints Interface ===\n");
    seq_puts(m, "Write format: COMPONENT:EVENT:CONFIDENCE\n");
    seq_puts(m, "Example: RAM:browser_data:890\n\n");
    seq_puts(m, "Last hint received:\n");

    spin_lock_irqsave(&hints_lock, flags);
    seq_printf(m, "  %s\n", hints_buffer);
    spin_unlock_irqrestore(&hints_lock, flags);

    return 0;
}

static int diana_hints_open(struct inode *inode, struct file *file)
{
    return single_open(file, diana_hints_show, NULL);
}

static const struct proc_ops diana_hints_ops = {
    .proc_open    = diana_hints_open,
    .proc_read    = seq_read,
    .proc_write   = diana_hints_write,
    .proc_lseek   = seq_lseek,
    .proc_release = single_release,
};

/*
 * /proc/diana/p2p_log — last 100 P2P messages
 */
static int diana_p2p_log_show(struct seq_file *m, void *v)
{
    p2p_log_to_proc(&diana_bus, m);
    return 0;
}

static int diana_p2p_log_open(struct inode *inode, struct file *file)
{
    return single_open(file, diana_p2p_log_show, NULL);
}

static const struct proc_ops diana_p2p_log_ops = {
    .proc_open    = diana_p2p_log_open,
    .proc_read    = seq_read,
    .proc_lseek   = seq_lseek,
    .proc_release = single_release,
};

/*
 * /proc/diana/cpu_report — CPU observer status
 */
static int diana_cpu_report_show(struct seq_file *m, void *v)
{
    cpu_get_stats(&diana_cpu, m);
    return 0;
}

static int diana_cpu_report_open(struct inode *inode, struct file *file)
{
    return single_open(file, diana_cpu_report_show, NULL);
}

static const struct proc_ops diana_cpu_report_ops = {
    .proc_open    = diana_cpu_report_open,
    .proc_read    = seq_read,
    .proc_lseek   = seq_lseek,
    .proc_release = single_release,
};

/* ================================================================
 * Module init and exit
 * ================================================================ */

static int __init diana_init(void)
{
    int ret;

    pr_info("╔═══════════════════════════════════════════════════╗\n");
    pr_info("║  DIANA-Nexus Kernel v1.0 — Initializing...       ║\n");
    pr_info("║  Distributed Intelligent Autonomous Neural Arch  ║\n");
    pr_info("╚═══════════════════════════════════════════════════╝\n");

    /* Initialize P2P bus */
    p2p_bus_init(&diana_bus);
    pr_info("DIANA: P2P bus initialized\n");

    /* Initialize CPU observer (passive!) */
    cpu_observer_init(&diana_cpu);

    /* Initialize all SYNAPSE components */
    component_ram_init(&diana_ram, &diana_bus, &diana_cpu);
    component_gpu_init(&diana_gpu, &diana_bus, &diana_cpu);
    component_ssd_init(&diana_ssd, &diana_bus, &diana_cpu);
    component_cache_init(&diana_cache, &diana_bus, &diana_cpu);

    /* Register kprobes */
    kp_kmalloc.pre_handler = kmalloc_pre_handler;
    ret = register_kprobe(&kp_kmalloc);
    if (ret < 0) {
        pr_warn("DIANA: kmalloc kprobe failed (%d), continuing...\n", ret);
    } else {
        pr_info("DIANA: kprobe on __kmalloc registered\n");
    }

    kp_vfs_read.pre_handler = vfs_read_pre_handler;
    ret = register_kprobe(&kp_vfs_read);
    if (ret < 0) {
        pr_warn("DIANA: vfs_read kprobe failed (%d), continuing...\n", ret);
    } else {
        pr_info("DIANA: kprobe on vfs_read registered\n");
    }

    kp_schedule.pre_handler = schedule_pre_handler;
    ret = register_kprobe(&kp_schedule);
    if (ret < 0) {
        pr_warn("DIANA: schedule kprobe failed (%d), trying alt...\n", ret);
        /* Try alternative symbol name */
        kp_schedule.symbol_name = "finish_task_switch";
        ret = register_kprobe(&kp_schedule);
        if (ret < 0)
            pr_warn("DIANA: schedule kprobe alt also failed (%d)\n", ret);
        else
            pr_info("DIANA: kprobe on finish_task_switch registered\n");
    } else {
        pr_info("DIANA: kprobe on scheduler registered\n");
    }

    /* Create /proc/diana/ directory */
    proc_diana_dir = proc_mkdir("diana", NULL);
    if (!proc_diana_dir) {
        pr_err("DIANA: failed to create /proc/diana/\n");
        goto cleanup_kprobes;
    }

    /* Create /proc/diana/stats */
    proc_stats = proc_create("stats", 0444, proc_diana_dir,
                             &diana_stats_ops);
    if (!proc_stats)
        pr_warn("DIANA: failed to create /proc/diana/stats\n");

    /* Create /proc/diana/hints (read + write) */
    proc_hints = proc_create("hints", 0666, proc_diana_dir,
                             &diana_hints_ops);
    if (!proc_hints)
        pr_warn("DIANA: failed to create /proc/diana/hints\n");

    /* Create /proc/diana/p2p_log */
    proc_p2p_log = proc_create("p2p_log", 0444, proc_diana_dir,
                               &diana_p2p_log_ops);
    if (!proc_p2p_log)
        pr_warn("DIANA: failed to create /proc/diana/p2p_log\n");

    /* Create /proc/diana/cpu_report */
    proc_cpu_report = proc_create("cpu_report", 0444, proc_diana_dir,
                                  &diana_cpu_report_ops);
    if (!proc_cpu_report)
        pr_warn("DIANA: failed to create /proc/diana/cpu_report\n");

    pr_info("DIANA: /proc/diana/ interface created\n");
    pr_info("╔═══════════════════════════════════════════════════╗\n");
    pr_info("║  DIANA-Nexus Kernel v1.0 — READY                 ║\n");
    pr_info("║  Components: RAM, GPU, SSD, CACHE                ║\n");
    pr_info("║  CPU Mode: PASSIVE OBSERVER (commands: 0)        ║\n");
    pr_info("║  P2P Bus: ACTIVE                                 ║\n");
    pr_info("║  SYNAPSE: frequency-table + userspace LSTM       ║\n");
    pr_info("╚═══════════════════════════════════════════════════╝\n");

    return 0;

cleanup_kprobes:
    unregister_kprobe(&kp_kmalloc);
    unregister_kprobe(&kp_vfs_read);
    unregister_kprobe(&kp_schedule);
    return -ENOMEM;
}

static void __exit diana_exit(void)
{
    pr_info("DIANA: shutting down...\n");

    /* Unregister kprobes */
    unregister_kprobe(&kp_kmalloc);
    unregister_kprobe(&kp_vfs_read);
    unregister_kprobe(&kp_schedule);
    pr_info("DIANA: kprobes unregistered\n");

    /* Remove /proc entries */
    if (proc_cpu_report)
        proc_remove(proc_cpu_report);
    if (proc_p2p_log)
        proc_remove(proc_p2p_log);
    if (proc_hints)
        proc_remove(proc_hints);
    if (proc_stats)
        proc_remove(proc_stats);
    if (proc_diana_dir)
        proc_remove(proc_diana_dir);
    pr_info("DIANA: /proc/diana/ removed\n");

    /* Destroy P2P bus (frees message log) */
    p2p_bus_destroy(&diana_bus);

    pr_info("╔═══════════════════════════════════════════════════╗\n");
    pr_info("║  DIANA-Nexus Kernel — UNLOADED                   ║\n");
    pr_info("║  CPU commands issued during session: %llu         ║\n",
            diana_cpu.commands_issued);
    pr_info("╚═══════════════════════════════════════════════════╝\n");
}

module_init(diana_init);
module_exit(diana_exit);
