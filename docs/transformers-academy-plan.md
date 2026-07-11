# Transformers from Scratch: The TinyStories Academy - Course Plan

Status: planning. Nothing built yet. We build lesson by lesson, and Avi validates each
lesson as a student before we move on.

This is the single source of truth for the plan. We will keep it updated as we go.

---

## 1. What we are building

A self-paced English course that teaches transformer architecture from first principles by
building a small GPT that writes children's stories, all runnable on CPU. It follows the
ideas of the reference project at `c:\Projects\Tinystories`, but is rebuilt fresh, one
lesson at a time, on Avi's Django learning platform.

The course content is English. The platform around it stays Hebrew (sidebar, buttons,
certificate text, page direction). Only the lesson bodies, titles, and the course
description are English. Flipping the chrome to English is explicitly out of scope.

Audience: people who can already write Python and want to understand how LLMs actually
work. Difficulty is advanced.

---

## 2. Architecture: two repos that point at each other

### Repo A - the course (lives in the Render platform)

- A normal `Course` record, lessons are `Video` records with an empty `bunny_video_id`
  (text-only lessons). Body is `notes_markdown`.
- No in-system Python execution. Code is shown as plain fenced ```python blocks, not
  runnable Pyodide cells. Each lesson tells the student to run the matching notebook in
  their own Jupyter.
- Lesson text is authored as committed Markdown in
  `data/course_materials/<slug>/course_manifest.json` and seeded with
  `python manage.py load_course_from_manifest <slug>`. Committed, reproducible, deploys
  with the repo.

### Repo B - the notebooks (new standalone GitHub repo)

- The thing the student clones and runs. Built here as a new directory with its own git
  and GitHub remote.
- Contains: one Jupyter notebook per lesson, the requirements file, the full TinyStories
  dataset (committed so everything runs offline), a README, and a `.gitignore` that
  excludes the `env/` virtualenv and training outputs (checkpoints).
- Notebooks are adapted from the reference project's existing `.ipynb` files (already
  known to run), not written from scratch. The course text is written fresh in English.

### How they connect

- Course-level `CourseMaterial` link points to Repo B on GitHub.
- Per-lesson `Video.github_file` links each lesson to its specific notebook.
- A lesson reads: explain the concept in text with code excerpts, then "open notebook NN
  in your cloned repo and run it."

---

## 3. Locked decisions

| Decision | Choice |
|---|---|
| Granularity | ~24 one-concept lessons (one idea per lesson, one notebook each) plus a capstone |
| Completion / certificate | Certificate issues on completing the lessons and submitting the capstone (a reflection where the student shares a story their own trained model generated). Plus light, non-gating self-check quizzes on lessons with a clear right answer. |
| Content storage | Committed manifest JSON, seeded to prod via `load_course_from_manifest` |
| Training data | Commit the full ~44MB TinyStories dataset into Repo B (works offline) |
| Language | Lesson content English, platform chrome stays Hebrew |

---

## 4. Confirmed details

| Item | Value |
|---|---|
| Course title | Transformers from the Ground Up - Building TinyStories |
| Slug | `transformers-from-scratch` |
| Taxonomy | difficulty `advanced`, category `foundations` (domain `ai` to set in studio if needed) |
| Repo B location | `C:\Projects\tinystories-academy` |
| Repo B remote | <https://github.com/avisalmon/tinystories-academy> (public) |
| Video | None for now. Avi adds videos after the lesson text is sharpened and tested. |

### Known issue to resolve before lesson 1

`load_course_from_manifest` skips any manifest lesson that has no `bunny_video_id`
(see `app/management/commands/load_course_from_manifest.py` lines 81-86). Because this
course is text-only, the loader needs a small, safe change so a lesson with
`notes_markdown` but no video is still created. To be done and approved before lesson 1.

---

## 5. Curriculum

A Getting Started setup lesson, then a Foundations module that builds neural-network basics
(up to a working handwritten-digit classifier) before the transformer-specific modules,
ending with a capstone plus an optional bonus module. Lessons are a flat ordered list; each
title carries its module so the list reads as grouped. One concept per lesson, one notebook
per lesson. The course grows as long as it needs to be genuinely good; it is not capped at a
fixed count. (Revised 2026-07-02: added a neural-network foundations arc, lessons 3-6, and
moved Embeddings to 7 so the foundations sit together and Embeddings leads into attention.)

### Getting Started
1. Setup and how this course works - clone the repo, create the env venv, install deps,
   launch Jupyter, run the setup-check notebook; how each lesson pairs a reading with one notebook

### Module 1 - Foundations (tensors and neural-network basics)
2. Tensors and shapes - the [batch, seq, dim] mental model
3. Linear layers - matrix multiplication, nn.Linear, weights and bias
4. Activation functions - why nonlinearity; ReLU and sigmoid, and GELU (the one the transformer uses)
5. What is a neural network? - high-level theory, no code: the linear-plus-activation stack and the
   show-guess-measure-nudge learning loop, seen live in the TensorFlow Playground. No notebook, no assignment
6. Build a neural network - a small MLP: layers, forward pass, softmax, parameter count
7. Softmax - turn logits into a probability distribution (exponentiate then normalize); the
   temperature knob that sharpens or flattens; the same softmax reused later in the loss, attention,
   and sampling. Interactive explorer + notebook
8. Datasets and DataLoaders - load real MNIST (28x28 handwritten digits) with torchvision; Dataset
   vs DataLoader, transforms, batches, flattening for an MLP, and the epoch/batch vocabulary
9. Loss: cross-entropy - measuring how wrong a prediction is; cross-entropy as softmax plus negative
   log-likelihood (built on Lesson 7); nn.CrossEntropyLoss takes the logits directly
10. Gradients and backpropagation - what a gradient is, autograd and loss.backward(), the optimizer
    and the learning rate; a gradient-descent widget for the learning-rate intuition
11. Recommended watch (neural networks, visually) - optional pause before building the loop: four
    3Blue1Brown videos on what a network is, gradient descent, and backprop, using digit recognition.
    No notebook, no practice, skippable
12. The training loop - put it together: epochs and the forward-loss-backward-step loop, train the
    MLP on MNIST, and measure test accuracy
13. Embeddings - turning token ids into vectors; the bridge from plain neural nets to sequence models

### Module 2 - Attention
14. Attention intuition - why attention
15. Dot-product attention - Q, K, V, scores, softmax, weighted sum
16. Scaled attention - why divide by sqrt(d_k)
17. Causal masking - the autoregressive constraint
18. Multi-head attention - parallel heads, split and concat

### Module 3 - The Transformer Block
19. Layer normalization
20. Feed-forward network - the MLP and GELU
21. Residual connections - skip connections and gradient flow
22. The full transformer block - pre-norm assembly

### Module 4 - Tokenization
23. Why tokenize - characters vs words vs subwords
24. BPE from scratch - byte-pair merges by hand
25. Train your tokenizer - train BPE on TinyStories, encode and decode

### Module 5 - Building GPT
26. Config and positional embeddings
27. The GPT model - stacking blocks, the LM head, weight tying
28. Putting it together - forward pass, parameter count, sanity checks

### Module 6 - Training
29. Dataset and dataloader - stories into training batches (reuses the DataLoader idea from Module 1)
30. Loss and the training loop - next-token cross-entropy and AdamW (reuses Module 1's training loop)
31. Full training run - train the model on CPU end to end, checkpointing
32. Tips and troubleshooting - LR warmup and decay, overfitting, reading the loss

### Module 7 - Generation
33. Sampling strategies - greedy, temperature, top-k, nucleus (top-p), repetition penalty
34. Generation in practice - prompt the model, write stories, save outputs

### Capstone
35. Capstone - share a story your own trained model generated (reflection). Completing
    this plus the lessons issues the certificate.

### Bonus (optional, built last if wanted)
- Attention visualization - heatmaps of what heads learned
- Scaling and your own experiments

---

## 6. Anatomy of a single lesson

Each lesson on the platform contains:

1. A short English `notes_markdown` body: motivation, the concept explained plainly, code
   excerpts in plain ```python blocks, and the key takeaways.
2. A "do this now" pointer to the matching notebook in Repo B (via `Video.github_file`).
3. Optionally a single multiple-choice self-check quiz (`LessonQuiz`, not gating).

The matching notebook in Repo B is the hands-on part: the student runs and tweaks it in
their own Jupyter.

No emojis and no em dashes in the lesson content, per Avi's house style.

---

## 7. Build workflow

### Phase 0 (once, after the open items are confirmed)
- Scaffold Repo B: new directory, git init, README, requirements.txt, `.gitignore`
  (excludes `env/` and checkpoints), the committed dataset, an empty `notebooks/` folder.
- Scaffold Repo A: create `data/course_materials/<slug>/course_manifest.json` with the
  course-level metadata and an empty lessons list, seed the unpublished `Course`, add the
  `CourseMaterial` link to Repo B.

### Per-lesson loop (repeat 26 times)
1. Claude writes lesson NN: the English `notes_markdown` in the manifest, plus the
   matching notebook NN in Repo B.
2. Avi runs notebook NN in his own Jupyter (`env` venv, `pip install -r requirements.txt`)
   and reads the lesson on his dev runserver. Tries it as a student.
3. Avi gives feedback, Claude revises until it is right.
4. Lock the lesson, re-seed dev with `load_course_from_manifest`, move to the next.

### Periodic
- Commit both repos. Push Repo B to GitHub. Deploy the Render course on Avi's word.

### Finish
- Publish the course, enable the certificate, polish the landing copy.

---

## 8. Progress tracker

Legend: [ ] not started, [~] in progress, [x] done.

| # | Lesson | Notes (Repo A) | Notebook (Repo B) | Avi validated |
|---|---|---|---|---|
| 0 | Phase 0 scaffold | [x] | [x] | [ ] |
| 1 | Setup and how this course works | [x] | [x] | [ ] |
| 2 | Tensors and shapes | [x] | [x] | [ ] |
| 3 | Linear layers | [x] | [x] | [ ] |
| 4 | Activation functions | [x] | [x] | [ ] |
| 5 | What is a neural network? (theory, no notebook) | [x] | n/a | [ ] |
| 6 | Build a neural network | [x] | [x] | [ ] |
| 7 | Softmax | [x] | [x] | [ ] |
| 8 | Datasets and DataLoaders | [x] | [x] | [ ] |
| 9 | Loss: cross-entropy | [x] | [x] | [ ] |
| 10 | Gradients and backpropagation | [x] | [x] | [ ] |
| 11 | Recommended watch (3B1B, no notebook) | [x] | n/a | [ ] |
| 12 | The training loop (train MLP on MNIST) | [x] | [x] | [ ] |
| 13 | Embeddings | [x] | [x] | [ ] |
| 14 | Attention intuition | [ ] | [ ] | [ ] |
| 15 | Dot-product attention | [ ] | [ ] | [ ] |
| 16 | Scaled attention | [ ] | [ ] | [ ] |
| 17 | Causal masking | [ ] | [ ] | [ ] |
| 18 | Multi-head attention | [ ] | [ ] | [ ] |
| 19 | Layer normalization | [ ] | [ ] | [ ] |
| 20 | Feed-forward network | [ ] | [ ] | [ ] |
| 21 | Residual connections | [ ] | [ ] | [ ] |
| 22 | The full transformer block | [ ] | [ ] | [ ] |
| 23 | Why tokenize | [ ] | [ ] | [ ] |
| 24 | BPE from scratch | [ ] | [ ] | [ ] |
| 25 | Train your tokenizer | [ ] | [ ] | [ ] |
| 26 | Config and positional embeddings | [ ] | [ ] | [ ] |
| 27 | The GPT model | [ ] | [ ] | [ ] |
| 28 | Putting it together | [ ] | [ ] | [ ] |
| 29 | Dataset and dataloader (stories) | [ ] | [ ] | [ ] |
| 30 | Loss and the training loop (GPT) | [ ] | [ ] | [ ] |
| 31 | Full training run | [ ] | [ ] | [ ] |
| 32 | Tips and troubleshooting | [ ] | [ ] | [ ] |
| 33 | Sampling strategies | [ ] | [ ] | [ ] |
| 34 | Generation in practice | [ ] | [ ] | [ ] |
| 35 | Capstone | [ ] | [ ] | [ ] |
| B1 | Attention visualization (bonus) | [ ] | [ ] | [ ] |
| B2 | Scaling and experiments (bonus) | [ ] | [ ] | [ ] |

Note: Lessons 5 and 11 are text-only (no notebook, no assignment): 5 is theory (TensorFlow Playground)
and 11 is a recommended-watch page (3Blue1Brown videos). The training material is split across lessons
8-12 (Datasets, Loss, Backprop, Recommended watch, Training loop) using formal MNIST via torchvision.
The foundations arc (1-12) is complete and the dev lesson list is contiguous 1-13. Next is Module 2
(Attention), starting at lesson 14.
