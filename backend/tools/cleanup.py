# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import os

import redis


def cleanup(client, prefix):
    nb, memory = 0, 0
    for key in client.keys(f"{prefix}:*"):
        if key.endswith(b"all:all"):
            continue

        key_memory = client.memory_usage(key)
        nb += 1
        memory += key_memory
        print(f"Removing {key_memory}b for {key}")

        client.delete(key)

    print(f"Removed {nb} keys for {memory} bytes")


if __name__ == "__main__":
    client = redis.from_url(os.environ["REDIS_URL"])
    cleanup(client, "overall:mozilla-central")
