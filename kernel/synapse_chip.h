/* SPDX-License-Identifier: GPL-2.0 */
/*
 * DIANA-OS — SYNAPSE Chip Intelligence (Kernel Space)
 *
 * Frequency-table based pattern learning in kernel space.
 * The heavy LSTM runs in userspace and sends hints via /proc/diana/hints.
 *
 * Author: Sahidh — DIANA Architecture
 */

#ifndef _DIANA_SYNAPSE_CHIP_H
#define _DIANA_SYNAPSE_CHIP_H

#include <linux/types.h>
#include <linux/spinlock.h>

#define SYNAPSE_PATTERN_SIZE    64
#define SYNAPSE_HISTORY_SIZE    32
#define SYNAPSE_NAME_LEN        16
#define SYNAPSE_CONFIDENCE_SCALE 1000  /* Fixed-point: 1000 = 100% */

struct synapse_chip {
    char name[SYNAPSE_NAME_LEN];
    spinlock_t lock;

    /* Pattern frequency table: event_a -> event_b => count */
    uint32_t pattern_table[SYNAPSE_PATTERN_SIZE][SYNAPSE_PATTERN_SIZE];
    uint32_t event_count;

    /* Recent event circular buffer */
    uint8_t history[SYNAPSE_HISTORY_SIZE];
    uint8_t history_head;
    uint8_t history_len;

    /* Statistics */
    uint64_t predictions_made;
    uint64_t predictions_correct;
    uint64_t prefetch_actions;
    uint64_t wait_actions;
    uint64_t patterns_learned;

    /* Last prediction for verification */
    uint8_t last_prediction;
    uint32_t last_confidence;  /* Fixed-point /1000 */
};

/* Initialize a SYNAPSE chip with the given name */
void synapse_init(struct synapse_chip *chip, const char *name);

/* Observe an event — updates frequency table and history */
void synapse_observe(struct synapse_chip *chip, uint8_t event_id);

/* Predict next event — returns event_id and confidence (0-1000) */
uint8_t synapse_predict(struct synapse_chip *chip, uint32_t *confidence);

/* Feedback: was the last prediction correct? */
void synapse_learn(struct synapse_chip *chip, bool was_correct);

/* Apply a hint from userspace LSTM (via /proc/diana/hints) */
void synapse_apply_hint(struct synapse_chip *chip, uint8_t event_id,
                        uint32_t confidence);

/* Get prediction accuracy as percentage (0-100) */
uint32_t synapse_get_accuracy(struct synapse_chip *chip);

/* Reset all state */
void synapse_reset(struct synapse_chip *chip);

#endif /* _DIANA_SYNAPSE_CHIP_H */
