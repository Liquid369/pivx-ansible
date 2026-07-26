# Testnet6 Seed Nodes

Candidate seed data for the `2026_testnet6` PIVX branch (PR not yet submitted).
**Nothing is hardcoded in chainparams yet** — decision pending on fixed seeds
vs. a DNS seeder behind a domain (e.g. the way `dnsseed.liquid369.wtf` serves
mainnet). Both paths are prepared below.

## Dedicated seeder instances (high-conn, always-on)

These run `maxconnections=256`, `dnsseed=0`, and are the bootstrap-mining
wallets during Phase 2:

| Instance | Address | Region |
|---|---|---|
| tn6-cb1-seed01 | `169.58.75.147:51534` | EU Nuremberg |
| tn6-cb2-seed02 | `62.146.176.174:51534` | US St. Louis |
| tn6-cb3-seed03 | `209.126.84.12:51534` | US St. Louis |

## Option A — fixed seeds (`contrib/seeds/nodes_test.txt`)

`generate-seeds.py` consumes `<ip>:<port>` lines and emits the
`chainparams_seed_test[]` array for `src/chainparamsseeds.h`. Candidate list
(seeders + one v4 masternode slot per remaining host, default port entries
listed first — servicebit filtering prefers them):

```
169.58.75.147:51534
62.146.176.174:51534
209.126.84.12:51534
66.94.119.202:51474
169.58.75.146:51474
169.58.75.144:51474
169.58.75.143:51474
169.58.75.142:51474
62.146.173.20:51474
94.72.121.81:51474
[2a02:c207:2346:5868::1]:51494
[2605:a140:2346:5863::1]:51494
[2605:a141:2346:5865::1]:51494
```

## Option B — DNS seeder behind a domain

Point a testnet6 subdomain (e.g. `testnet.dnsseed.liquid369.wtf`) at a
pivx-seeder crawler instance and replace the fuzzbawls entries in
`CTestNetParams::vSeeds` when the PR is finalized. The crawler needs one of
the seeder instances above as its bootstrap peer.

## Tor onion candidates (generated 2026-07-26, port 51514)

```
27at7bsmh4r6ulamu33huyrrr23vd3ulaosckyaglgrimanp7ngxzaqd.onion:51514
ahznq5kwpd6xwxfggg2ooy545ts2f72l7flu3rbcyxoog7fjjjd5j7ad.onion:51514
u2gjinpoyfehafgl4ibmpkqxkuoz2gfw5zm5spirumjl2pyu5ghwzcad.onion:51514
```

(tor-mn05 on cb1/cb2/cb3; all 18 onion addresses live in host_vars.
`generate-seeds.py` accepts `<onion>.onion:<port>` lines directly if the
fixed-seeds route is chosen.)
