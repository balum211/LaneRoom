# Source documents

| File | Document | Real or synthetic | Pages used |
|---|---|---|---|
| `jbht_2025.pdf` | J.B. Hunt Transport Services, Inc. Form 10-K for fiscal year 2025 (filed 2026-02-24, accession 0001437749-26-005294) | **Real**, SEC EDGAR | 1-63 |
| `chrw_2025.pdf` | C.H. Robinson Worldwide, Inc. Form 10-K for fiscal year 2025 (filed 2026-02-13, accession 0001043277-26-000009) | **Real**, SEC EDGAR | 1-108 (exhibit index dropped) |
| `odfl_2025.pdf` | Old Dominion Freight Line, Inc. Form 10-K for fiscal year 2025 (filed 2026-02-24, accession 0001193125-26-067161) | **Real**, SEC EDGAR | 1-98 (exhibit index dropped) |
| `armada_profile_synthetic.pdf` | "Armada Freight Services" carrier profile, built from `armada_profile_synthetic.html` | **SYNTHETIC** | 1-5 |

The three 10-Ks were downloaded from EDGAR (`https://www.sec.gov/Archives/edgar/data/...`) as the primary HTML
documents with a generic research User-Agent, then printed to PDF with headless Microsoft Edge so that every passage
keeps a page number for citations. Page numbers in LaneRoom refer to these PDFs, not to the filers' printed page
footers.

**Armada is privately held and files nothing with the SEC.** Its profile is illustrative data written by Team 24 for
the demo. It does not describe any real company named Armada, and none of its figures are real reported results.
Every page of the PDF carries a "SYNTHETIC PROFILE" banner, every chunk is flagged `synthetic` in the index, and the
app, memo and README label it as such. The Judge caps any provider backed only by synthetic data at 25% of a lane.

The **lane scorecard** (`data/scorecard/shipper_scorecard_synthetic.csv`, made by `scripts/make_scorecard.py`) is
also synthetic: public filings never report a shipper's tender acceptance, on-time %, rate per mile or claims % by
carrier.

To rebuild the search index after changing these files: `python scripts/build_index.py semantic`.
