/* SPDX-License-Identifier: GPL-2.0 */
/*
 * DIANA-OS — SYNAPSE Chip Intelligence (Kernel Space)
 *
 * Simple frequency-table based pattern learning.
 * No floating point — all integer arithmetic.
 * Real LSTM runs in userspace, sends hints via /proc/diana/hints.
 *
 * Author: Sahidh — DIANA Architecture
 */

#include <linux/kernel.h>
#include <linux/string.h>
#include "synapse_chip.h"

void synapse_init(struct synapse_chip *chip, const char *name)
{
    memset(chip, 0, sizeof(*chip));
    strscpy(chip->name, name, SYNAPSE_NAME_LEN);
    spin_lock_init(&chip->lock);
    chip->last_prediction = 0xFF;
    chip->last_confidence = 0;
}

void synapse_observe(struct synapse_chip *chip, uint8_t event_id)
{
    unsigned long flags;
    uint8_t prev;

    if (event_id >= SYNAPSE_PATTERN_SIZE)
        return;

    spin_lock_irqsave(&chip->lock, flags);

    /* Update frequency table: previous event -> this event */
    if (chip->history_len > 0) {
        prev = chip->history[(chip->history_head - 1 + SYNAPSE_HISTORY_SIZE)
                              % SYNAPSE_HISTORY_SIZE];
        if (prev < SYNAPSE_PATTERN_SIZE) {
            chip->pattern_table[prev][event_id]++;
            chip->patterns_learned++;
        }
    }

    /* Add to circular history buffer */
    chip->history[chip->history_head] = event_id;
    chip->history_head = (chip->history_head + 1) % SYNAPSE_HISTORY_SIZE;
    if (chip->history_len < SYNAPSE_HISTORY_SIZE)
        chip->history_len++;

    chip->event_count++;

    /* Check if last prediction was correct */
    if (chip->last_prediction != 0xFF) {
        if (chip->last_prediction == event_id) {
            chip->predictions_correct++;
        }
        chip->last_prediction = 0xFF;
    }

    spin_unlock_irqrestore(&chip->lock, flags);
}

uint8_t synapse_predict(struct synapse_chip *chip, uint32_t *confidence)
{
    unsigned long flags;
    uint8_t last_event, best_event = 0;
    uint32_t best_count = 0, total = 0;
    int i;

    spin_lock_irqsave(&chip->lock, flags);

    if (chip->history_len == 0) {
        spin_unlock_irqrestore(&chip->lock, flags);
        *confidence = 0;
        return 0;
    }

    /* Get the most recent event */
    last_event = chip->history[(chip->history_head - 1 + SYNAPSE_HISTORY_SIZE)
                                % SYNAPSE_HISTORY_SIZE];

    if (last_event >= SYNAPSE_PATTERN_SIZE) {
        spin_unlock_irqrestore(&chip->lock, flags);
        *confidence = 0;
        return 0;
    }

    /* Find the most frequent successor */
    for (i = 0; i < SYNAPSE_PATTERN_SIZE; i++) {
        uint32_t count = chip->pattern_table[last_event][i];
        total += count;
        if (count > best_count) {
            best_count = count;
            best_event = (uint8_t)i;
        }
    }

    chip->predictions_made++;
    chip->last_prediction = best_event;

    if (total > 0)
        chip->last_confidence = (best_count * SYNAPSE_CONFIDENCE_SCALE) / total;
    else
        chip->last_confidence = 0;

    *confidence = chip->last_confidence;

    spin_unlock_irqrestore(&chip->lock, flags);

    return best_event;
}

void synapse_learn(struct synapse_chip *chip, bool was_correct)
{
    unsigned long flags;

    spin_lock_irqsave(&chip->lock, flags);

    if (was_correct) {
        chip->predictions_correct++;
        chip->prefetch_actions++;
    } else {
        chip->wait_actions++;
    }

    spin_unlock_irqrestore(&chip->lock, flags);
}

void synapse_apply_hint(struct synapse_chip *chip, uint8_t event_id,
                        uint32_t confidence)
{
    unsigned long flags;
    uint8_t last_event;

    if (event_id >= SYNAPSE_PATTERN_SIZE)
        return;

    spin_lock_irqsave(&chip->lock, flags);

    /* If LSTM is confident, boost the frequency table entry */
    if (confidence > 700 && chip->history_len > 0) {
        last_event = chip->history[(chip->history_head - 1 +
                      SYNAPSE_HISTORY_SIZE) % SYNAPSE_HISTORY_SIZE];
        if (last_event < SYNAPSE_PATTERN_SIZE) {
            /* Boost by confidence-proportional amount */
            chip->pattern_table[last_event][event_id] +=
                (confidence / 100);
            chip->prefetch_actions++;
        }
    }

    spin_unlock_irqrestore(&chip->lock, flags);
}

uint32_t synapse_get_accuracy(struct synapse_chip *chip)
{
    unsigned long flags;
    uint32_t accuracy;

    spin_lock_irqsave(&chip->lock, flags);

    if (chip->predictions_made == 0) {
        spin_unlock_irqrestore(&chip->lock, flags);
        return 0;
    }

    accuracy = (uint32_t)((chip->predictions_correct * 100) /
                           chip->predictions_made);

    spin_unlock_irqrestore(&chip->lock, flags);

    return accuracy;
}

void synapse_reset(struct synapse_chip *chip)
{
    unsigned long flags;
    char name_backup[SYNAPSE_NAME_LEN];

    spin_lock_irqsave(&chip->lock, flags);
    memcpy(name_backup, chip->name, SYNAPSE_NAME_LEN);
    memset(chip, 0, sizeof(*chip));
    memcpy(chip->name, name_backup, SYNAPSE_NAME_LEN);
    spin_lock_init(&chip->lock);
    chip->last_prediction = 0xFF;
    spin_unlock_irqrestore(&chip->lock, flags);
}
