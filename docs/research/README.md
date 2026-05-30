# babook.co.il Research — README

## What's Here

This folder contains comprehensive research on the AI community platform market, competitive landscape, and a feature skeleton for babook.co.il.

### Documents

1. **[competitive_landscape.md](competitive_landscape.md)** — **START HERE**
   - Deep-dive on 8 competitors (DeepLearning.AI, Kaggle, Google Colab, GitHub Copilot, Replit, Hugging Face, Coursera, OpenAI)
   - Feature comparison table
   - Market gaps identified
   - Monetization opportunities

2. **[feature_skeleton.md](feature_skeleton.md)** — **Detailed Feature Breakdown**
   - Full specification of all 5 scopes (Training 3-level, Community 5-feature, Token Provider, Service Store, etc.)
   - Implementation phases
   - Success metrics
   - What to avoid

3. **[research_summary.md](research_summary.md)** — **Analysis + Recommendations**
   - Key learnings
   - 5 critical questions for Avi to answer
   - Recommended MVP stack (with rationale)
   - What NOT to do

4. **[scope_quick_reference.md](scope_quick_reference.md)** — **TL;DR Cheat Sheet**
   - 1-page summary of each scope
   - Effort vs. revenue matrix
   - MVP recommendations
   - Questions for prioritization

---

## How to Use This

### If you have 15 minutes:
- Read: [scope_quick_reference.md](scope_quick_reference.md)
- Answer the "Questions for Avi" section

### If you have 1 hour:
- Read: [research_summary.md](research_summary.md)
- Skim: [competitive_landscape.md](competitive_landscape.md) (focus on gaps section)

### If you want to deep-dive:
- Read all 4 documents in order
- Focus on: feature comparisons, market opportunity matrix, MVP recommendations

---

## Key Findings (TL;DR)

### **Market Opportunity**
- No existing platform combines: multi-level training + community + token provisioning + service marketplace + meetups
- **babook can fill this gap** — especially for Israel-based AI professionals

### **Competitive Advantages**
1. Integrated platform (vs. siloed competitors)
2. Community-first design (vs. content-only or tools-only)
3. Token control (Copilot + OpenAI resale)
4. Local advantage (Hebrew-speaking community)
5. Multi-sided marketplace

### **Recommended MVP Focus**
- **User segment:** Self-taught + junior developers
- **Primary revenue:** Token resale (Copilot, OpenAI credits)
- **Primary scope:** Practical level (co-coding, agents, MCP)
- **Timeline:** 8-12 weeks
- **Key features:** Practical courses + forums + skill marketplace + token integration

### **Market Segments Validated**
| Segment | Size | Pain | babook Solution |
|---------|------|------|-----------------|
| Junior devs (Israel) | 2-5K | Can't afford tools + training | Bundled skills + Copilot discount |
| ML researchers | 100-200 | Isolation, no peer network | Community + mentorship + compute |
| AI teams at startups | 100s | Need trained staff quickly | Corporate training + hiring board |
| Freelance advisors | 50s | Hard to find clients | Marketplace + credibility badges |

### **Revenue Model (Year 1 Potential)**
- Token resale (Copilot): **₪300K-1M** ⭐
- Skill marketplace commission: **₪50-300K**
- OpenAI credits: **₪100-500K**
- Advisor marketplace: **₪200K-1M** (slower ramp)
- Corporate training: **₪200K-1M** (B2B, longer cycle)
- Newsletters + sponsorships: **₪50-200K**

**Total Year 1 potential:** ₪1-4M (if all sources active)

---

## Next Steps (For Avi)

1. **Answer the 6 critical questions** (in research_summary.md)
   - Which user segment first? (user / practical / deep / corporate)
   - Revenue focus? (subscriptions / marketplace / tokens / corporate)
   - Which scope MVP? (training / community / tokens / services)
   - Geography? (Israel-only / diaspora / global)
   - Sync vs async? (live coding / recorded courses / mix)
   - Advisor marketplace timeline? (soft-launch soon / later)

2. **Validate with target users** (optional but recommended)
   - Survey 10 Israeli junior devs: "Would you pay ₪X for Copilot bundled with courses?"
   - Survey 5 ML researchers: "What would help your learning most?"
   - Interview 3 potential advisors: "Would you be interested in marketplace?"

3. **Lock Chapter 2 scope** (once you decide MVP focus)
   - Based on answers above, we'll define:
     - Exact feature set for MVP
     - Sprint breakdown (2-week sprints)
     - Success metrics
     - Risk & dependencies

4. **Start Chapter 2 spec** (in docs/main_spec.md)
   - Vision, scope, acceptance criteria
   - Epic-2 sprints
   - Requirements and decisions

---

## Research Methodology

**Sources:**
- Direct visit to 8 competitor platforms
- Feature extraction from landing pages + product tours
- Pricing analysis
- Market size estimates (based on user counts, public metrics)

**Limitations:**
- Pricing data is public; actual margins unknown
- We didn't conduct user interviews (your idea to validate)
- Research is May 2026 snapshot; competitors evolving

---

## What We Didn't Research (Out of Scope)

- Legal/regulatory for marketplace (advisor vetting, payment processing)
- Payment infrastructure (Stripe, payment gateways)
- Growth marketing strategies
- Detailed financial modeling
- Competitor sensitivity analysis (if we build, how will Kaggle/GitHub react?)

---

## Questions?

All documents are in `docs/research/`. Add more as you find them:
- `market_validation.md` (after user interviews)
- `financial_model.md` (once you decide MVP)
- `competitor_tracking.md` (ongoing monitoring)

---

**Research is complete. Ready to build Chapter 2?**

Go to [research_summary.md](research_summary.md) and answer the 6 critical questions. Then we'll lock the spec.
