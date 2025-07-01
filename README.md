I was thinking, what if we try to make the most secure blockchain ? You know, without vulnerabilities, fast, that heals itself, that verifies itself, a new one, for example, start from the beginning, with an empty Petoron folder, and write it in Python.

It's June 25, 2025 - 22:48 and it's almost done, I've been testing for about 3 weeks now, but I'm lost in time, it seems like it was just morning and it's already evening, I'm drinking green tea right now, I love green tea, it's relaxing )))

1 person.
1 dream.
1 goal.
1 on 1 with yourself.

And so, the basic information from me will be written below, but the documentation will be written by the community themselves by looking at the open source code.

Something like this:
- Full decentralization and open source
- The limit of mined coins is only 1 000 000 000 (1 billion), they can only be mined through mining.
- The transfer fee is 0 ADC until the last coin is mined, after which the smart commission mechanism is activated and miners receive the entire transaction fee as soon as it is included in the block. The more transactions the miner records, the more profitable it is for the miner.
- The entire structure is written for use by the terminal, including the interface. Without any third-party dependencies.
- Cube A + Cube B is a uniquely designed wallet authorization system, based on rubik's cube combinations, you will see it 1 time when you create your wallet. there are no passwords and seed phrases or mnemonic phrases that you are used to. (So, you forgot it or lost it? - No one can help you. No one. Ever. The cube is not stored anywhere.)
- Is brute-force possible, what do you think? (256^32 + salt)
- PoW: Double PoW (MicroPrefix + hash)
- Data Format: struct+binary
- File-Level Lock: (fcntl/msvcrt)
- Protection against race condition
- Self-recovery of chain, balances,daily_rewards on accidental deletion
- Verification of the entire .bin chain via verifier, in case of detection of fakes, the network is not shut down, it heals itself without intervention and pulls up the files that were corrupted.
- Fork detection: Hash checkpoints + sig
- Peer sync: auto - peers.bin via TCP
- Protocol: TCP socket bin
- god_eye is a unique file that does not affect the network, but protects you from making malicious changes to your device. The network doesn't know god_eye exists, but god_eye knows everything about the network. The first time you run it, god_eye.hashes will be created and it means that your files will be protected from modification
- da_vinci is a network protection against counterfeiting

There is a lot you can write here, but what's the point? Maybe it's better to look at the code? :)


There are no official Petoron social media pages, no website, no customer support, no email, no contact for feedback. There is only this code and you who are reading this text. I'm giving it to you.

I don't trust anyone. Not even myself.
Remember. The network is alive. Petoron is alive. I'm here. I am with you.

./setup_all.sh # For new network members (initial setup)

export PETH_ROLE=server # This command is required ONLY for VPS nodes (to add to peer-to-peer networks)

./run_all.sh # Start a Petoron network node.

Welcome!

---
So, wait, did you really think all that was true? Ha ha :)))
I made it all up, everything written here is complete nonsense and fiction, I just have a good imagination, or maybe not :)))))
