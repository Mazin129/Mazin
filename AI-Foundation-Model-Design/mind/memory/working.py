"""
working  —  Working Memory: the active scratchpad for one turn.  [CORTEX-OS §3.1]

A small, bounded set of slots holding the current goal, retrieved facts, and partial
reasoning while Vio answers. Capacity is limited (Miller's 7±2); when full, the
lowest-salience slot is displaced (interference-based forgetting, not a hard window).
Cleared/refreshed each interaction. Pure in-RAM, no persistence.
"""

from __future__ import annotations


class WorkingMemory:
    def __init__(self, capacity=7):
        self.capacity = capacity
        self.slots = []            # list of {"key","value","salience"}

    def put(self, key, value, salience=0.5):
        for s in self.slots:                       # update in place if key exists
            if s["key"] == key:
                s["value"], s["salience"] = value, max(s["salience"], salience)
                return
        self.slots.append({"key": key, "value": value, "salience": salience})
        if len(self.slots) > self.capacity:        # displace the least salient
            self.slots.sort(key=lambda s: -s["salience"])
            self.slots = self.slots[:self.capacity]

    def get(self, key, default=None):
        for s in self.slots:
            if s["key"] == key:
                return s["value"]
        return default

    def items(self):
        return [(s["key"], s["value"]) for s in sorted(self.slots, key=lambda x: -x["salience"])]

    def clear(self):
        self.slots = []

    def __len__(self):
        return len(self.slots)

    def __repr__(self):
        return f"WorkingMemory({[s['key'] for s in self.slots]})"
