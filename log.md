HELLO WORLD!

This is me logging what I actually did on my project so far, by days.

Day 1: 

Experimenting with the SNN's:

Well so I guess some things that are important to remember is the: 

v = voltage, signifying how charged up a neuron is currently, it is kind of like water in a bucket and every new input will be adding water

threshold = fill line, so basically when the "water" reaches the threshold, the neuron would fire a spike and the "bucket empties(meaning v = 0.0) afterwards"

leak= the whole in the bucket. so basically, each step the voltage loses a certain amount v = v* leak so with leak = 0.9, it loses 10 percent. Lower leak value = "bigger hole." 

Verilog wires are directional, meaning info flows in only one direction.

finished up basics on verilog!


Day 2: 

note:

for defining vectors its dimensions come before its name 

so 
wire [99:0] my_vector;      // Declare a 100-element vector

learned about vector gates, 
logical operators (!, ||, &&, treat whole vector as a single true/false and give back 1 bit. )


bitwise operators(~ , |, &) work on each bit seperately and give back a result as wide as the inputs 

^ means xor

Almost done with vectors


Day 3:

Finished vectors.

Make sure to plan out circuit before hand


## 2026-10-13 — 3-input neuron with inhibition, verified in Verilog

**What I built**
- Upgraded the integer LIF neuron from one input current to three spike inputs (A, B, C), each with its own weight: +300, +50, and −150 (inhibitory).
- Each tick: total = sum of weights of inputs that fired; v = v − (v >> 3) + total; spike and reset to 0 when v ≥ 256.
- Python reference model plus a hand-designed 16-tick test covering: strong input alone, weak input alone, weak input building up over time, excitatory + inhibitory together, inhibitory alone (negative voltage), and recovery from negative voltage.
- Verilog version (`lif_neuron`) with a testbench that loads packed input spikes via `$readmemh`.

**Result**
- Verilog output matches the Python reference exactly on all 16 ticks, including the edge case where voltage hits 257 (just over threshold) and negative voltages (−77 → −67).

**Bugs and lessons**
- Widened voltage from 9 to 16 bits: weights and voltages up to ~350 plus negative values didn't fit.
- Made voltage, total, weights, and threshold `signed`. Mixing signed and unsigned values makes Verilog treat the whole expression as unsigned, silently turning negatives into large positives.
- Used `? :` instead of multiplying by the 1-bit spike input, so the 1-bit (unsigned) wire never enters the math.
- Replaced bit-slicing for the leak with `>>>`, which keeps the sign and rounds down like Python's `>>`.
- Fixed the threshold comparison to use a signed constant (`16'sd256`); an unsigned constant would make negative voltages trigger false spikes.
- `np.savetxt` on a list of lists writes three space-separated values per line; packed each row into one number (A=4, B=2, C=1) so `$readmemh` reads one value per tick.

**Next**
- Self-checking testbench (PASS or first mismatch).
- 3-neuron chain (A → B → C plus an inhibitory link), Python first, then Verilog with module hierarchy.
