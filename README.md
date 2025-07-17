langent
=======

Wireless language out of entropy

Langent is intended to use a shared entropy source, either generated from an RNG shared on a network device or a wireless broadband receiver to seed a mapping function or hash function that will encode data transmission packets based on the environmental entropy.

For example, if Alice wants to transmit a file to Bob, and both Alice and Bob share a source of entropy, then Alice can create a dictionary of hashed values where the data can overlap in the random data from the source of entropy, and as long as the encoding scheme is shorter than the compressed data in the shared entropy, then Alice can share the encoding and location of the transmission to Bob, and Bob, who has a perfect copy of the shared entropy can decode Alice's file.

Another version uses a neural net, to learn an arbitrary encoding stream that can map on top (xor) of the random noise that represents the data being sent across.

the hypothesis I wish to prove or disprove is that, this is a viable transmission strategy and that I can trade time for space encoding.


---

No, this is not a viable transmission strategy because it relies on solving a problem that is even harder than the one it's trying to address. The core concept you've described is a variation of a cryptographic primitive known as a **One-Time Pad (OTP)**, and it suffers from the same well-understood and fatal flaw for practical use: **the key distribution problem**.

Your hypothesis is ultimately disproven by the practical and theoretical impossibilities of implementing the required shared entropy source.

***

### The "Perfect Copy" Problem

The entire system hinges on Alice and Bob having a **perfectly identical and synchronized stream of entropy**. This is the first and most significant point of failure.

* **Environmental Noise:** Using a "wireless broadband receiver" to capture environmental entropy at two different locations (Alice's and Bob's) will **never** produce identical data streams. Even receivers placed side-by-side will generate different data due to microscopic differences in their electronics, thermal noise, and quantum effects. The signals they receive will also differ due to their unique positions in space. Their entropy sources will diverge almost instantly.
* **Shared RNG:** Using a "shared RNG" means you must first transmit the entropy stream from the generator to both Alice and Bob. This transmission must be perfectly secure and error-free. If you already have a channel capable of securely transmitting this massive amount of random data (the pad), you could just use that channel to send your file directly. You've simply moved the problem, not solved it.

***

### Analysis of Proposed Methods

Let's assume you magically solved the shared entropy problem. The two methods you proposed still face critical issues.

#### 1. The Hashing/Mapping Method

This method is a form of compression that uses the shared entropy stream `E` as an external dictionary. The goal is to represent the file `F` as a series of pointers to locations in `E`.

* **Probability is Against You:** A truly random data stream is, by definition, devoid of predictable patterns. The probability of finding a specific, meaningful chunk of your file (e.g., the 16 bytes representing the phrase "Project Proposal") within a random stream is astronomically low.
* **The Scale Is Impractical:** To have a reasonable chance of finding all the necessary chunks to reconstruct even a small file, the shared entropy stream `E` would need to be trillions of times larger than the file itself.
* **The Encoding Is Inefficient:** Even if you found matches, the encoding would not save space. To specify a location in a multi-terabyte entropy stream, each pointer would need to be several bytes long. For short data matches, the pointer would be larger than the data it represents. For example, finding an 8-byte chunk of data might require a 10-byte pointer, resulting in **negative compression**.

#### 2. The Neural Net / XOR Method

This is functionally identical to a **One-Time Pad (OTP)**. The message `M` is XORed with a segment of the shared entropy `E` to produce ciphertext `C`.

$$C = M \oplus E_{\text{segment}}$$

Bob, who has the same `E`, can easily decrypt it:

$$M = C \oplus E_{\text{segment}}$$

* **Security:** This method is, in fact, **perfectly secure** if the entropy stream is truly random, secret, and never reused.
* **The Catch (Key Distribution):** The fatal flaw of the OTP is that the secret key (the "pad," or your entropy stream `E`) must be **at least as long as the message** and must be securely distributed to the recipient beforehand. As mentioned earlier, if you can securely deliver a 1 GB secret key, you can securely deliver a 1 GB file. The OTP does not solve the problem of secure transmission; it *relies* on it.

The neural network adds complexity without benefit. Its role would be to select or manipulate parts of the entropy stream, but this doesn't change the fundamental need to pre-share that stream.

***

### Hypothesis: Trading Time for Space

You proposed trading "time for space encoding."

* For the **Hashing Method**, you are indeed trading time (an impossibly long search) and pre-shared space (an impossibly large entropy pool) for transmission space. However, the trade is so poor that it's not feasible. You gain no benefit.
* For the **OTP/XOR Method**, the "time" cost is not in encoding (XOR is extremely fast), but in the **upfront time and effort** to generate and securely deliver the massive entropy pad. The "space" cost is the storage required for this pad, which must equal the total size of all messages you ever intend to send.

In conclusion, the Langent hypothesis is disproven. It is not a viable transmission strategy because it cannot overcome the physical impossibility of creating a shared entropy source and re-creates the key distribution problem inherent in One-Time Pads. 💡
