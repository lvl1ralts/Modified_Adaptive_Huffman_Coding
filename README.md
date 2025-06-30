# Modified Adaptive Huffman Coding

This repository contains an implementation of the **Modified Adaptive Huffman Coding** algorithm for large alphabets (whole words) as described in Mikhail Tokovarov’s 2017 paper. 

[📄 View the Research Paper ](docs/paper.pdf)

---

# Chat-Huffman-Py

A modern Python 3 CLI chat application that **compresses** every message with a modified _Adaptive Huffman Coding_ algorithm before it hits the wire and **decompresses** it on arrival – saving bandwidth while remaining completely transparent to users.

---

## Features

• Word-level adaptive Huffman encoding with dedicated **NCW** (New-Coming-Word) and **NYT** (Not-Yet-Transmitted) leaves.  
• Fully asynchronous TCP chat server supporting multiple clients.  
• Lightweight CLI client (pure standard library).  
• Zero third-party runtime dependencies.

---

## 📝 Introduction

Adaptive Huffman Coding dynamically updates its code tree as it processes input. The classic FGK algorithm uses a single NYT (“Not Yet Transmitted”) node for both indicating where to attach new symbols and signaling their arrival. Tokovarov’s **modified** approach introduces a separate **NCW** (“New‑Coming Word”) node:

1. **NYT node** — marks where in the tree new symbols (words) are inserted.  
2. **NCW node** — signals that the next bits are the raw ASCII representation of a brand‑new word.  

By treating **whole words** as symbols, this method achieves better compression on natural language text, and the separate NCW node reduces overhead when new words arrive frequently.

**🖼️ Visual Comparison: Traditional vs Modified Huffman Tree<br>
Note how NCW separates out new word logic from insertion point.**

![Figure 3: Modified vs Unmodified Word‑Level Tree](docs/figure3.png)  

---

## 📖 Background & Algorithm Overview

1. **Tree Structure**  
   - Each node has a **weight**, **key number**, and optionally stores a word.  
   - The **NYT** leaf always has weight 0 and the smallest key.  
   - The **NCW** leaf also starts with weight 0 and is used solely to mark new‑word signals.
  
**🖼️ Tree Example: Word-Based Huffman Tree<br>
Shows how the word-level tree evolves as new tokens are added**

![Figure 1: Example Huffman Tree](docs/figure1.png)  

2. **Encoding**  
   - If a word already exists in the tree, output its current code (path from root) and update the tree.  
   - Otherwise:
     1. Output the **NCW** node’s code.  
     2. Update the NCW node’s weight.  
     3. Output the word’s ASCII bytes (8‑bit each) followed by a delimiter `<DEL>`.  
     4. Insert the new word under the old NYT node and update its weight.  

3. **Decoding**  
   - Read bits until you match a leaf’s code:
     - If it’s a **normal** leaf, recover the word and update the tree.  
     - If it’s **NCW**, update NCW, then read 8‑bit ASCII chunks until `<DEL>`, reconstruct the new word, insert it, and update.  

<!-----

## 🔧 Prerequisites

- A modern C++ compiler (GCC, Clang, or MSVC) supporting C++11 or later.  
- Standard C++ library—no external dependencies.

---

## Setup

```bash
# Clone or copy the repo and enter the directory
$ cd chat_huffman_py

# (Optional) create an isolated virtual environment
$ python3 -m venv .venv
$ source .venv/bin/activate

# Install requirements (none at runtime, but do it anyway for future extensibility)
$ pip install -r requirements.txt
```

---

## Starting the server

```bash
# Default port 9000
$ python -m chat_huffman_py.server
# Custom port
$ python -m chat_huffman_py.server 1234
```

## Launching a client

bash
# Syntax: python -m chat_huffman_py.client <host> [port] [username]
$ python -m chat_huffman_py.client 127.0.0.1 9000 Alice
$ python -m chat_huffman_py.client 127.0.0.1 9000 Bob

---

## 🚀 Building & Running

1. **Compile**

      ```bash
   g++ -std=c++17 -O2 code.cpp -o huffman

2. **Run**

      ```bash
      ./huffman

      Enter text to encode and decode:
      I am Human living in a Human World.

      Tokens to be encoded:
      'I' 'am' 'Human' 'living' 'in' 'a' 'Human' 'World.'

      Encoded Bitstream:
      1I|1am|1Human|1living|1in|1a|0010World.|

      Decoded Text:
      I am Human living in a Human World.

      Verification:
      Success
-->
---

## 📊 Performance & Compression

The following figures demonstrate the bit-efficiency of this model vs classical Huffman variants.


**🖼️ SOBR Comparison (Sent-to-Original Bits Ratio)**

![Figure 5: SOBR Comparison](docs/figure5.png)

**🖼️ SSOBR Delta Across Variants**

![Figure 6: SSOBR Differences](docs/figure6.png)
