# Testnet6 Seed Nodes

Candidate seed data for the 2026_testnet6 branch, PR not submitted yet.
Nothing is hardcoded in chainparams yet, still deciding between fixed seeds
and a DNS seeder behind a domain (same setup as dnsseed.liquid369.wtf on
mainnet). Both lists below stay current either way.

## Dedicated seeder instances

These run maxconnections=256, dnsseed=0, and hold the bootstrap mining
wallets for Phase 2:

| Instance | Address | Region |
|---|---|---|
| tn6-cb1-seed01 | `169.58.75.147:51534` | EU Nuremberg |
| tn6-cb2-seed02 | `62.146.176.174:51534` | US St. Louis |
| tn6-cb3-seed03 | `209.126.84.12:51534` | US St. Louis |

## Option A: fixed seeds (contrib/seeds/nodes_test.txt)

generate-seeds.py takes ip:port lines and emits the chainparams_seed_test[]
array for src/chainparamsseeds.h. Candidates, default-port entries first
since servicebit filtering prefers them:

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

## Option B: DNS seeder behind a domain

Point a testnet6 subdomain (e.g. testnet-seed.<domain>) at a seeder crawler
and swap the fuzzbawls entries out of CTestNetParams::vSeeds when the PR is
finalized. The crawler bootstraps from one of the seeder instances above.
Note the seed subdomain has to be NS delegated, it cannot sit behind the
Cloudflare proxy.

## Tor onions (generated 2026-07-26, port 51514)

```
27at7bsmh4r6ulamu33huyrrr23vd3ulaosckyaglgrimanp7ngxzaqd.onion:51514
ahznq5kwpd6xwxfggg2ooy545ts2f72l7flu3rbcyxoog7fjjjd5j7ad.onion:51514
u2gjinpoyfehafgl4ibmpkqxkuoz2gfw5zm5spirumjl2pyu5ghwzcad.onion:51514
```

tor-mn05 on cb1/cb2/cb3, all 18 onion addresses live in host_vars.
generate-seeds.py accepts onion:port lines directly if we go fixed seeds.
