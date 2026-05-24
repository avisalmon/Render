# babook.co.il Research — README

> **Current strategy note (May 2026):** This folder contains historical market research. The active product direction is now the authority-platform pivot in [../main_spec.md](../main_spec.md): babook is a free credibility and lead-generation platform for Avi's corporate AI training. Token resale, Copilot resale, skill marketplace, and broad community-platform ideas are parked until the corporate funnel is already producing inbound leads. Start with [research_3.md](research_3.md), DEC-19, and DEC-19a in [../main_spec.md](../main_spec.md).

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
- Read: [research_3.md](research_3.md)
- Then read [../main_spec.md Chapter 2](../main_spec.md)

### If you have 1 hour:
- Read: [research_3.md](research_3.md)
- Skim: [research_summary.md](research_summary.md) as historical context only
- Check DEC-19 and DEC-19a in [../main_spec.md](../main_spec.md)

### If you want to deep-dive:
- Read all 4 documents in order
- Treat early MVP recommendations as superseded
- Focus on: market gaps, corporate-training demand signals, and what strengthens Avi's authority funnel

---

## Key Findings (TL;DR)

### **Current Market Opportunity**
- Companies need practical AI training and trustworthy guidance now.
- babook's best first job is to make Avi look credible, reachable, and easy to hire.
- The site should optimize for inbound corporate training inquiries, not consumer subscription complexity.

### **Current Competitive Advantages**
1. Avi's real-world corporate AI training experience
2. Hebrew-first local market fit
3. Fast, direct WhatsApp/contact conversion
4. Public proof assets: flagship course, guides, answers, and community content
5. Optional future platform expansion once demand is proven

### **Current MVP Focus**
- **User segment:** HR, L&D, engineering leaders, and managers buying AI training for teams
- **Primary revenue:** Corporate workshops, bootcamps, and keynotes sold outside the platform
- **Primary scope:** Corporate training page + lead capture + newsletter capture + one flagship course
- **Timeline:** Ship the conversion page first, then build proof/content around it
- **Key features:** `/corporate/`, WhatsApp CTA, lead form, email notification, basic SEO, one excellent flagship course

### **Market Segments Validated**
| Segment | Size | Pain | babook Solution |
|---------|------|------|-----------------|
| Junior devs (Israel) | 2-5K | Can't afford tools + training | Bundled skills + Copilot discount |
| ML researchers | 100-200 | Isolation, no peer network | Community + mentorship + compute |
| AI teams at startups | 100s | Need trained staff quickly | Corporate training + hiring board |
| Freelance advisors | 50s | Hard to find clients | Marketplace + credibility badges |

### **Revenue Model (Current Priority)**
- Corporate training: **primary**
- Newsletter/sponsorships: later, after audience exists
- Courses: proof asset and lead magnet first, paid library later if useful
- Token resale, skill marketplace, advisor marketplace: parked future options

**Total Year 1 potential:** ₪1-4M (if all sources active)

---

## Next Steps (For Avi)

1. **Ship the lean `/corporate/` conversion MVP**
   - Hero, service tiers, FAQ, WhatsApp CTA, lead form, email notification, SEO, mobile polish.

2. **Add newsletter capture**
   - Capture warm visitors who are interested but not ready to book a call.

3. **Publish one flagship course**
   - Use it as proof of teaching quality and as a lead magnet for corporate training.

4. **Re-evaluate parked platform ideas only after signal**
   - Forum, marketplace, token resale, and enterprise dashboards return only if they make corporate inquiries grow faster.

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

**Research is complete. Chapter 2 is now locked around the authority-platform path.**

Use [../main_spec.md](../main_spec.md) and [../backlog.md](../backlog.md) as the active delivery source of truth.
