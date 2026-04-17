---
title: "VigenereSolver-ng"
summary: "Advanced vigenere cipher brute force solver utilizing classical techniques combined with LLM-based techniques for english plaintext scoring, as well as other math tricks for better approximations and key length/char predictions."
tags: ["cryptography", "cryptanalysis", "vigenere"]
published: true
date: 2025-12-26
---

# VigenereSolver-ng

https://github.com/supasuge/VigenereSolver-ng

## Description
[VigenerSolver-ng](https://github.com/supasuge/VigenereSolver-ng)is an experimental Vigenère solver that fuses classical statistics, beam-search heuristics, and modern language-model scoring. It can recover keys, decrypt ciphertexts, visualise key-length evidence, and benchmark different decoder backends — including KenLM language model. The previously known best language model prior to the release of the transformer architecture of neural networks powering modern LLMs today.

## Project Goals

- [x] Fully decrypt a vigenere ciphertext with 0 knowledge of the key.
- [x] Understand and implement classical attacks defined in various research papers over time against the vigenere cipher.
- [x] Utilize modern-ish Language Model/NLP processing-based techniques to improve the overall accuracy.


## TODO's and Contributing

- [ ] Add particle optimization swarm markov chains
- [ ] Improve data normalization/pre-processing and post-processing.
- [ ] Switch from a LN-LM Model to a more modern architecture trained on a large corpus of english text first, then fine-tuned for the vigenere cipher.