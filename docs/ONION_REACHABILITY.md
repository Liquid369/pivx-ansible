# Onion masternodes are invisible without a SOCKS proxy on clearnet nodes

Found 2026-09-08 while crawling testnet6. Verified against PIVX Core source, not inferred.

## Symptom

A crawl of testnet6 returns only IPv4 and IPv6 addresses. Slots 4 and 5 (`tor-mn05`,
`tor-mn06`) publish `onion:51474` and are MN-capable, but no `.onion` address appears in
any peer's `getaddr` response.

Measured on 169.58.75.142: 33 addresses received, all accounted for, **zero torv3, zero
dropped as stale**. The addresses are not being lost in transit or filtered by age. They
are never sent, because no clearnet node has them.

## Cause

`net_processing.cpp:1566`

    // Do not store addresses outside our network
    if (fReachable)
        vAddrOk.push_back(addr);

`fReachable` is `IsReachable(addr)`, which is `!vfLimited[net]`. A node only adds an
address to addrman if it considers that network reachable. Onion reachability is off by
default (`init.cpp:1339`, `SetReachable(NET_ONION, false)`) and is only enabled by
`-proxy` or `-onion` (`:1354`, `:1373`).

Our clearnet instances set no proxy. They receive the Tor masternodes' addresses, evaluate
them as unreachable, and discard them. `getaddr` can only return what addrman holds, so
onion masternodes are invisible fleet-wide.

`onlynet` compounds it. `init.cpp:1325-1327` marks every network **not** listed as
unreachable, so `onlynet=ipv6` on slots 2 and 3 makes those instances discard IPv4 and
onion addresses both. The fleet currently keeps three address books that barely overlap.

## Fix

Give clearnet instances a Tor SOCKS proxy, in `roles/pivx_instance/templates/pivx.conf.j2`:

    {% elif instance.protocol_class == 'ipv4' %}
    listen=1
    bind={{ instance.bind_addr }}
    externalip={{ instance.external_ip }}
    proxy=127.0.0.1:{{ tor_socks_port | default(9050) }}

`proxy=` sets `SetReachable(NET_ONION, true)`, after which the node stores onion addresses,
relays them, and serves them from `getaddr`.

## Two costs, both already documented in this repo

1. It needs a Tor daemon on every clearnet host. The template's own seed comment notes
   clearnet instances have no SOCKS proxy and that dialling an onion without one fails on
   every retry with "Cannot create socket: unsupported network".
2. Reachable means dialled. The same comment records the onion seeds spending roughly 88%
   of CPU in `b-pivx-addcon` rebuilding 3-hop circuits on retry. Thirteen clearnet hosts
   gaining onion reachability will start dialling onion peers, not merely storing them.

Consider `onlynet=ipv6` on slots 2 and 3 separately. It is arguably the larger problem: it
fragments the fleet's address books regardless of Tor.

## Why this matters beyond the crawler

This is the v6.0 PoSe cliff, reproducible on our own testnet.

PoSe has one trigger: exclusion from a mined final commitment
(`evo/deterministicmns.cpp:821`). Exclusion comes from
`CDKGSession::VerifyConnectionAndMinProtoVersions` marking a member bad when the local node
has had no successful **outbound** MNAUTH to it within 3600s. Inbound never counts
(`evo/mnauth.cpp:121`).

A clearnet node with no proxy cannot store an onion masternode's address, so it cannot dial
it, so it cannot complete MNAUTH, so it votes that member bad. If enough members agree, the
commitment mines and the Tor masternodes are PoSe-punished for being unreachable by a
majority that was configured unable to reach them.

**The configuration that hides onion nodes from a crawler is the configuration that would
PoSe-ban them.** Worth fixing on testnet before it is discovered on mainnet.

Background: `PIVX/.agent/IPV6-TOR-WORK.md` and memory `FACTS.md` F16.

## Addendum — verified on the fleet 2026-09-08

Reproduced, then corrected in two places. Fleet only; mainnet operator wording is
Q14 and is not touched here.

### Use `-onion`, not `-proxy`

The fix above says `proxy=`. That is the wrong directive for a clearnet node.
`init.cpp` sets a proxy for **every** network when `-proxy` is given:

    SetProxy(NET_IPV4, addrProxy);
    SetProxy(NET_IPV6, addrProxy);
    SetProxy(NET_ONION, addrProxy);
    SetReachable(NET_ONION, true);

so `proxy=` pushes the node's IPv4 and IPv6 traffic through Tor as well. `-onion`
sets the proxy for onion alone and leaves clearnet direct, with the same
`SetReachable(NET_ONION, true)`. That is all this needs.

Behind `pivx_clearnet_onion_reach`, default false. Only tn6-cb10 has it.

### Both costs are smaller than recorded

A Tor daemon on every clearnet host is already there: `tor` is active with SOCKS
on 9050 on all 15 fleet hosts, so this adds no dependency.

The ~88% in `b-pivx-addcon` was the self-addnode loop, a node dialling its own
advertised address and rebuilding a circuit per retry. That was a config bug and
the template excludes self from the seed list now. It is not what onion
reachability costs.

Measured instead, matched instances at comparable peer counts, 60s sample:

| instance | onion | cpu/60s | peers |
|---|---|---|---|
| tn6-cb9-v4-mn02 | no | 1% | 17 |
| tn6-cb10-v4-mn02 | yes | 6% | 19 |

About 5 points of one core per instance. Hosts sit at load 0.4-2.8 with 4-8
vCPU, so this is affordable, but it is not free either.

### Fleet address books before the change

Addrman contents by class, `getnodeaddresses 0`, fleet universe ~147:

| class | nodes | avg total | ipv4 | ipv6 | onion |
|---|---|---|---|---|---|
| ipv4, no proxy | 58 | 96.8 | 45.9 | 50.9 | **0.0** |
| ipv4, `onion=` | 1 | 147.0 | 46.0 | 51.0 | 50.0 |
| ipv6, `onlynet=ipv6` | 50 | 50.7 | **0.0** | 50.7 | **0.0** |
| tor, `onlynet=onion` | 50 | 50.0 | **0.0** | **0.0** | 50.0 |

All 58 unproxied clearnet instances held zero onion addresses. The single
exception is tn6-cb1-seed01, which was given `onion=` on 2026-08-21 for an
unrelated masternode broadcast failure and has held the full 147 since.

`onlynet` is the larger half and it cuts both ways. ipv4 sees 66% of the network,
ipv6 35%, tor 34%. Every cohort is blind to the other two, not just clearnet to
onion. For a mixed LLMQ that means most member pairs cannot dial each other in
either direction, so the bad-votes are mutual rather than aimed at Tor. Left
alone: cohort isolated DKG appears to be what the 45/50/50 sizing against minSize
16 exists to test, so changing it changes the experiment.

### Crawler, before and after

`pivx-crawler --testnet`, branch 2026_crawler_modernization.

169.58.75.142, no proxy:

    found 33 addresses, by family: {"ipv4": 15, "ipv6": 18}
    addrv2 ids received: [("ipv4", 15), ("ipv6", 18)], dropped as stale: 0

94.72.121.81, `onion=` enabled:

    found 33 addresses, by family: {"ipv4": 10, "onion": 12, "ipv6": 11}
    addrv2 ids received: [("ipv4", 10), ("ipv6", 11), ("torv3", 12)], dropped as stale: 0

`dropped as stale: 0` on both sides settles it. The addresses were not aged out
or lost in transit, they were never in addrman to send.

Two things about the crawler itself. It parses the seed as `Ip::Ip4` on the
default port, so a node on another port cannot be targeted and
169.58.75.147:51534 fails hostname lookup. And `CRAWLER_DISCORD_WEBHOOK` is read
with `?`, so a crawl that has already done all its work exits `Error: NotPresent`
without one.
