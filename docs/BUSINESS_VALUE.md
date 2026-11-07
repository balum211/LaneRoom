# Business value: ROI, net savings and benefits

> **Illustrative.** Carrier rates, tender acceptance, on-time % and claims come from the **synthetic** lane
> scorecard, and the drivers below use stated assumptions. The method is real; the dollar figures are demo data.
> Every assumption can be changed in the app (**Business value** tab → *Assumptions*) and in
> `src/laneroom/value.py`.

## Why an AI tender committee

| # | Pain today | What LaneRoom changes |
|---|---|---|
| 1 | **Reviews take weeks.** Procurement and finance read each carrier's 10-K and scorecard and build the case; legal reviews the contract terms. A lane review takes weeks to a month or two of elapsed time. | The committee reads the 10-Ks and the scorecard, computes the figures and writes a cited memo in about a minute. A person reviews and approves. Legal still signs the contract; what disappears is the research and analysis time before it. |
| 2 | **Manual errors and bias.** Copy-paste mistakes in spreadsheets, and habits or relationships that favour an incumbent carrier. | Every claim cites a 10-K page or scorecard row, and a Verifier rejects claims that do not match their source (in the eval the planted false claim is caught 100% of the time). The same rules apply to every carrier: 60% cap, 10% floor, 80% acceptance floor, and a 25% cap for unaudited data. The AI can make mistakes too, which is why claims are verified and a human approves. |
| 3 | **Adding carriers is rigid and slow**, so fewer carriers compete for the freight. | A new carrier is one more document plus its scorecard rows, so it can be compared on the same day, and more qualified carriers keep bidding. Compliance onboarding (operating authority, insurance, safety scores) is still a separate step; LaneRoom speeds up the evaluation, not the compliance checks. |
| 4 | **Backhaul and spot tenders do not wait.** A carrier's discounted backhaul capacity or a spot offer is gone in minutes to hours. | A decision in about a minute lets the shipper take discounted backhaul and spot capacity that a days-long process misses. |
| 5 | **Single-carrier risk.** One carrier's bad week (rejections, a peak-season squeeze) stops the lane. | Primary, secondary and backup carriers with capped shares; every qualified carrier keeps backup volume. |
| 6 | **No audit trail or memory.** The reasoning behind past awards lives in inboxes. | Each award is a memo with footnotes, a trace of every agent step and a logged human decision; mandates and approved awards are remembered for the next review. |
| 7 | **Service failures are expensive.** Late loads mean expediting, re-delivery and retailer on-time penalties; rejected tenders fall to the spot market at a premium. | The award weighs acceptance, on-time and claims, not just the quoted rate (see *Award mix* below). |
| 8 | **It does not scale.** A team can deeply review only a few lanes per cycle. | The same committee runs on every lane, every month, at a cost of cents per run. |

## How the value is calculated

For one lane, per year (`value.evaluate`):

| Driver | Formula | Default assumption |
|---|---|---|
| **Review time** | reviews/yr × (manual hours − review hours with AI) × hourly cost | 12 reviews, 40 h manual (procurement + legal), 1.5 h with AI, $85/h |
| **Backhaul / spot speed** | loads × backhaul share × (capture with AI − capture manual) × miles × contract rate × backhaul discount | 10% of loads, 80% vs 30% caught, 15% discount |
| **More bidders** | contract linehaul spend × rate pressure | 1% |
| **Award mix (landed cost)** | (even-split landed cost − committee landed cost) × loads | see below |
| **Cost of running it** | platform + LLM calls per run | $25,000 a year per lane, $0.05 per run |

**Landed cost per load** = miles × (acceptance × contract rate + rejections × spot rate) × (1 + claims %) + late share
× cost of a late load. Spot is 20% above the lane's average contract rate; a late load costs $250. Carriers whose rate
per mile is far from the lane's median (an LTL carrier on a truckload lane) are left out of the mix comparison, because
an LTL rate per mile is not the cost of a full truckload.

**Net savings** = sum of drivers − running cost. **ROI** = net savings ÷ (platform + LLM + human review cost).
**Payback** = that investment ÷ daily gross benefit.

The award-mix driver is reported **honestly and can be negative**. A balanced or service-first mandate pays a
premium for higher acceptance and on-time delivery, and that premium is shown as a cost, not hidden. The cost-first
mandate shows what the committee saves when cost leads.

## Results on the eight lanes (offline agents, default assumptions)

| Mandate | Lane | Review time | Backhaul speed | More bidders | Award mix | Net savings / yr | ROI | Payback |
|---|---|---|---|---|---|---|---|---|
| balanced | Dallas, TX to Atlanta, GA | $39,270 | $350,270 | $467,026 | -$527,941 | **$303,624** (+0.6%) | 1,144% | 29 days |
| balanced | Dallas, TX to Houston, TX | $39,270 | $139,465 | $185,954 | -$97,543 | **$242,146** (+1.3%) | 913% | 36 days |
| balanced | National LTL contract | $39,270 | $962,442 | $1,283,256 | -$1,654,033 | **$605,935** (+0.5%) | 2,284% | 15 days |
| balanced | Peak season surge (national) | $39,270 | $846,481 | $1,128,642 | $1,115,656 | **$3,105,049** (+3.0%) | 11,704% | 3 days |
| balanced | Chicago, IL to Los Angeles, CA | $39,270 | $459,479 | $612,638 | $729,192 | **$1,815,578** (+2.9%) | 6,843% | 5 days |
| balanced | Atlanta, GA to Miami, FL | $39,270 | $125,682 | $167,576 | -$114,701 | **$192,827** (+1.1%) | 727% | 44 days |
| balanced | Los Angeles, CA to Phoenix, AZ | $39,270 | $91,095 | $121,460 | -$16,094 | **$210,730** (+1.7%) | 794% | 41 days |
| balanced | Chicago, IL to Newark, NJ | $39,270 | $277,238 | $369,650 | $586,785 | **$1,247,943** (+3.5%) | 4,704% | 8 days |
| cost-first | Dallas, TX to Atlanta, GA | $39,270 | $340,739 | $454,319 | $355,082 | **$1,164,408** (+2.5%) | 4,389% | 8 days |
| cost-first | Dallas, TX to Houston, TX | $39,270 | $137,275 | $183,033 | $51,825 | **$386,403** (+2.0%) | 1,456% | 24 days |
| cost-first | National LTL contract | $39,270 | $933,953 | $1,245,271 | $1,654,033 | **$3,847,527** (+3.0%) | 14,502% | 3 days |
| cost-first | Peak season surge (national) | $39,270 | $723,983 | $965,311 | $1,226,649 | **$2,930,213** (+2.8%) | 11,045% | 3 days |
| cost-first | Chicago, IL to Los Angeles, CA | $39,270 | $459,479 | $612,638 | $729,192 | **$1,815,578** (+2.9%) | 6,843% | 5 days |
| cost-first | Atlanta, GA to Miami, FL | $39,270 | $123,255 | $164,340 | $113,612 | **$415,477** (+2.4%) | 1,566% | 22 days |
| cost-first | Los Angeles, CA to Phoenix, AZ | $39,270 | $90,052 | $120,069 | $76,527 | **$300,917** (+2.4%) | 1,134% | 30 days |
| cost-first | Chicago, IL to Newark, NJ | $39,270 | $240,504 | $320,672 | $488,988 | **$1,064,434** (+3.0%) | 4,012% | 9 days |

Loads per year are the request's weekly loads × 52, or the lane's 2025 tender volume when the request gives none.
Across the eight lanes: **about $7.7M net a year with a balanced mandate and $11.9M cost-first**, i.e. 0.5% to 3.5%
of landed freight cost, plus **462 procurement and legal hours a year per lane**. The ROI percentages look large
because a lane's freight spend ($10M to $100M+ a year) dwarfs the cost of running the committee. The percentage of
freight cost is the more useful number to compare.

**Service benefits** (Dallas → Atlanta, balanced): +1.4 points tender acceptance and +0.9 points on-time versus an
even split, about 228 late loads avoided and about 359 loads kept off the spot market a year, no carrier above 45%,
and every claim checked against a source.

## Limits

- All carrier figures are synthetic; real results depend on the shipper's own TMS data.
- Backhaul capture, rate pressure and the cost of a late load are assumptions; set them to the shipper's history.
- The model treats each lane on its own; network effects (carriers' backhaul needs across lanes) are not modelled.
- The committee recommends; a person approves and legal signs the contract.
