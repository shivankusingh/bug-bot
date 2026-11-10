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


## 2026-10-15: Neuron function refactor, 3-neuron chain, inhibitory interneuron

**What I built**
- Refactored the LIF neuron math into one reusable function: `neuron_model(total, v)` → returns `(new_v, spike)`.
  Re-ran the old 16-tick test and the Verilog self-checking testbench still printed PASS, so the refactor didn't change any results.
- Built a 3-neuron chain (A → B → C) in Python. One poke on A makes A, B, C fire on consecutive ticks; matched my hand prediction exactly.
- Added an inhibitory interneuron I (I → B, weight −400). 4-neuron network: A → B → C plus I → B.

**What I learned**
- **Function vs. loop:** the neuron function only does the math for ONE neuron (leak, add, threshold, reset).
  The loop does the bookkeeping: computes each neuron's input total, calls the function once per neuron, and stores the results.
  The function never needs the spike list, just `total` and `v`.
- **Each neuron keeps its own state:** its own voltage (`v_a`, `v_b`, …) and its own "did I fire last tick" note (`last_a`, …).
  These are set up before the loop; totals are recalculated inside the loop every tick.
- **One-tick synaptic delay (the domino rule):** a neuron only reacts to spikes from the *previous* tick.
  Each tick: (1) build all totals from last tick's spikes, (2) run every neuron, (3) only then overwrite the `last_` notes.
  This makes the result independent of the order of the code, handles loops in the wiring, and matches hardware,
  where every neuron updates on the same clock edge.
- **Multiplying by a spike works like an `if`:** `last_a * w_ab` gives the full weight if A fired and 0 if it didn't.
- **Weights belong to connections, not neurons:** a weight is how hard one neuron hits the next (A→B, B→C, I→B).
- **Outside inputs vs. neuron inputs:** the input table holds only outside pushes (sensors). Columns = outside inputs,
  not number of neurons. Neurons that aren't sensory only listen to other neurons.
- **Inhibition = a negative-weight connection:** the inhibitory neuron itself is normal (positive poke, fills up, fires);
  only its outgoing connection is negative. It only affects neurons it's wired to, and only when it spikes.
- **Lingering inhibition:** a scoop leaves the target's voltage negative, and the leak brings it back slowly,
  so later pushes can fail. (I fired on tick 2 → B was at −400 on tick 3 → A's +300 on tick 4 only reached −50.)
- **`>>` on negatives rounds down** (e.g., `-50 >> 3 = -7`); must match Verilog's `>>>`.
- **Why inhibition matters in the worm:** forward and backward command neurons suppress each other, so the robot
  commits to one direction when both ends are bumped (winner-take-all).

**Next**
- Save expected files for all 4 neurons → build the network in Verilog (parameterized weights, top module with 4 instances) → self-checking PASS.
- Then: wiring-list refactor in Python → real touch circuit from connectome data.


# bug-bot log: Oct 27, 2026

## Summary
Picked bug-bot back up after a break. Started refactoring the Python reference model from hardcoded per-neuron variables (`total_a`, `last_a`, ...) into a data-driven **sparse connection list**, so the same code can eventually run the full 302-neuron C. elegans connectome.

## What I did
- Reviewed my current 4-neuron network (A → B → C chain + inhibitory neuron I onto B) in both Verilog and Python.
- Set a workflow: I write the core RTL and model logic; Claude helps with tooling (testbenches, connectome parser, scripts). Rule: don't commit anything I can't explain line by line.
- Looked at EDA Playground alternatives. Plan: move to a local flow (Icarus/Verilator + cocotb + Surfer/GTKWave) so sims can read my golden-vector files directly.
- Decided to build the Python model with a sparse connection list instead of a dense matrix, to mirror how the hardware will store synapses.
- Wrote `connections` (one list of `(target, weight)` pairs per neuron) and the loop that computes each neuron's input from last step's spikes.
  - Test: `last_spikes = [1, 0, 0, 1]` gives `totals = [0, -100, 0, 0]` ✅
- Wrote `poke_connections` (poke 0 → A at 300, poke 1 → I at 300).

## What I learned
- **Connectivity as a matrix:** an N×N weight matrix `W[pre][post]`. A column is everything a neuron *listens to*; a row is everything it *sends to*. All neurons' input totals = spike vector × W.
- **Sparse storage:** most entries are zero (no connection). Store only real connections: the position in the outer list = the sender, and each pair = (receiver, weight). Each stored entry carries its own "address," so anything missing is 0. Since adding 0 changes nothing, skipping zeros doesn't change the answer.
- **Event-driven:** only neurons that spiked get their lists processed, so silent neurons cost nothing. This is a big reason neuromorphic hardware is efficient.
- **Scale:** worm = 302×302 ≈ 91k slots but only a few thousand real synapses (dense is fine in Python). Fly ≈ 140k neurons, so a dense matrix is impossible and sparse is required. FPGA memory is small, so hardware will be sparse even for the worm (later: CSR format).
- **Not every matrix is square:** input/sensor matrices are (#inputs × N).
- **Voltage vs. total:** voltage = the neuron's memory (a leaky bucket, carried between steps); total = input arriving *this* step (reset to 0 each step). They must stay separate because the leak is computed on the *old* voltage before input is added (e.g. v=80, input 300: correct = 370, adding first = 333).
- **Inhibition** just adds a negative weight into the same sum (300 + −400 = −100); it doesn't overwrite excitation.
- **Poke weight 300 > threshold 256**, so one poke = guaranteed spike. A poke into the inhibitory neuron must be *positive* so it fires; its *output* is what's negative.
- **Code structure:** setup (network definition, runs once) vs. per-step code (totals, loops, voltage update, runs inside the main loop).
- **Golden model caveat:** Python ints never overflow, so wrap/saturation must be done inside the model, not just masked at export.
- **Biology caveat:** most real C. elegans neurons use graded potentials, not spikes. LIF is a deliberate simplification.
- Python: `range(len(x))` not `.size()`; `for target, weight in pairs:` unpacks tuples.

## Mistakes I made (and fixed)
- Added weights to the **sender** (`totals[i]`) instead of the **receiver** (`totals[target]`).
- First poke loop iterated over the whole `pokes` schedule instead of the current `row`, used an `else` (pokes are independent), and hardcoded indices.
- Set poke → Inhib weight to −400 (should be +300).

## Known issues (later)
- Verilog: 16-bit `total`/`voltage` with no saturation (will wrap with many inputs); no voltage floor.
- One module instance per neuron doesn't scale to 302 → time-multiplexed core with voltages + synapse lists in memory.

## Next steps
1. Finish the poke loop (test: `row = [1, 1]` → `[300, 0, 0, 300]`).
2. Wrap neuron + poke loops into `compute_totals(last_spikes, row)`.
3. Plug into the main loop; confirm all six golden `.txt` files are identical to before.
4. Then: load the real connectome (Claude writes the parser; I decide weight scaling, excitatory vs. inhibitory, gap junctions).


# bug-bot log: Oct 28–29, 2026

## Summary
Loaded the real C. elegans connectome (300 neurons) into my Python model and got the touch test working in both directions: **head touch → the worm backs up, tail touch → it goes forward, and the brain goes quiet after each poke.** Getting there took a chain of experiments to track down a runaway where almost the whole brain locked on.

## What I did
- Added pipes (gap junctions) to my model: flow is computed from start-of-step voltages and written into `totals`, once per pipe, so charge is conserved.
- Claude wrote `connectome_parser.py` (Cook 2019 wiring + Fenyves 2020 signs). My decisions: weight = size × K, which rule decides each sign (`SIGN_ORDER`), the touch rule from Chalfie 1985.
- Wrote `touch_test.ipynb`: pokes into the touch sensors (ALML/ALMR/AVM for the head, PLML/PLMR/PVM for the tail), saving every step's voltages and spikes, and plotting with `plot_run.py`.
- Ran experiments to find and fix the runaway (tables below).
- Added my own **team rule** to the parser: between the 8 decision neurons, same team → +, opposite team → −.
- Added **spike packages to pipes**: when a neuron fires, each pipe partner gets `+size × PIPE_K` on the next step.

## Experiments: head touch
| # | K | "complex" links | Team rule | Result |
|---|---|---|---|---|
| 0 | 43 | + (fell to GABA rule) | ✗ | runaway: ~230 / 300 firing by step 5, all decision neurons locked on |
| 1 | 10 | + | ✗ | forward stayed off during the poke, but runaway after release |
| 2 | 43 | − | ✗ | smaller runaway: ~175 / 300 firing forever |
| 3 | 10 | − | ✗ | quiet after the poke, forward off, but backward almost silent (AVAL 1 spike, AVAR 0) |
| 4 | 10 | − | ✓ | **head → backward only (AVAL 6, AVAR 6), forward 0, quiet by step 24** ✅ |

Run 3's problem: AVD → AVA links were "complex", so the blanket guess made them brakes (AVDR → AVAR = −520). Two backward neurons were shutting each other down. The team rule fixed it (+520).

## Experiments: head + tail (80 steps), sweeping PIPE_K
| `PIPE_K` | Head: back / fwd spikes | Tail: back / fwd spikes | Quiet after tail? |
|---|---|---|---|
| 0 (no packages) | 12 / 0 | 0 / 2 | ✅ but tail too weak |
| 1 | 20 / 0 | 0 / 27 | ✅ by step 62 |
| 2 | 28 / 0 | 0 / 48 | ✅ by step 70 |
| 3 | 40 / 0 | 0 / 61 | ❌ runaway |
| 10 | 60 / 43 | 80 / 80 | ❌ runaway |

Picked **`PIPE_K = 1`**: works both ways, stops right after each poke, far from the runaway edge, and in hardware the package is just the raw size (no multiply).

## What I learned
- **Positive feedback loop:** the decision neurons were wired with all-+ loops, so once a few fired they kept firing each other forever. The network had ~3,100 + links and only ~550 − links, so almost no brakes.
- **Keys and locks:** the sender releases a chemical (key: ACh, Glu, GABA); the receiver has go locks (+) and stop locks (−). The sign table only says which locks *exist* (yes/no), not how many, so "complex" (both kinds) can't be resolved from the data.
- **Blanket guess:** one answer for every unknown link. It isn't accurate link by link; it's a default and a quick test of whether that group matters. Using "+" for complex was already a blanket guess.
- **Known rules beat blanket guesses** for the links that matter most (touch rule, team rule); the blanket only covers what's left.
- **`SIGN_ORDER` is the hierarchy, not the order of the `if`s:** each loop turn has one rule name, so only that rule's `if` can match. The first rule with an answer wins (`return` ends the function).
- **K lives in the parser:** chemical weights are pre-multiplied (size 12 × 10 = 120) and stored finished, like the FPGA's memory will be. Pipes stay raw-size, so the notebook scales them with `PIPE_K`.
- **Leveling-off rule:** with leak `v >> 3`, a steady input settles near **8 × input**. So any neuron getting a steady +32 or more per step eventually fires, however small K is. That's why lowering K only delayed the runaway.
- **Why pipes needed spike packages:** a firing neuron resets to 0, so its pipes see an "empty tank" and pass nothing. The tail sensors reach forward mostly through pipes, so tail touch was weak. This comes from LIF's reset (real worm neurons mostly use graded potentials), not a coding bug.
- **Ping-pong:** pipes are two-way and always +, so if `size × PIPE_K ≥ 256` two neurons can fire each other forever (PVCL ↔ PVCR, size 67). That's why `PIPE_K` must be tiny.
- **Tipping point:** PVCR was already settling at 160 from PVM alone; the pipe's +8 per step pushed it to ~224, and small extra inputs tipped it over. A small change can matter a lot near threshold.
- Change one knob at a time, predict before running, and compare against the last run.

## Mistakes I made (and fixed)
- Pipe loop first wrote into `voltages` (order-dependent); fixed to write into `totals`.
- Forgot `.copy()` when saving voltages, so every saved row was the same list.
- Notebook kept using the old `connectome_all.py` after regenerating it: restart the kernel after rerunning the parser.
- Edited the existing table line in `decide_sign` instead of adding a new `if` (it returned 4 values instead of 3 and would have made every table link −).
- Nested two poke schedules inside one list instead of joining them with `+`, so nothing got poked.

## Next steps
1. Optional test: poke head and tail at the same time (`[1,1]`) and see which team wins the race.
2. Roadmap step 4: local Verilog sim flow (Icarus/Verilator + cocotb + Surfer/GTKWave).
3. Pipes (flow + spike packages) still need to go into Verilog, then new golden files.


# bug-bot log: Oct 29, 2026 (part 2): motors

## Summary
Checked whether the decision actually reaches the muscles. It didn't: the command neurons chose correctly, but the backward motors never fired. Fixed it by restructuring my sign rules into one data-driven **circuit rule**, plus one-way command → motor links. Now head touch → backward motors, tail touch → forward motors, and the brain is quiet after each poke.

## What I did
- Added a motor panel to the plot ("Do the motors follow?"): VA/DA = backward motors, VB/DB = forward motors.
- Found that AVAL (backward command) → DA05 (backward motor) was −140: the table said "complex", and my blanket "complex = −" turned teammates into brakes again.
- Replaced the touch rule and team rule with one table + one rule:
  - `CIRCUIT`: a tag for 53 known neurons, `(team, layer)`. Team = which direction it pushes; layer = SENSOR, COMMAND or MOTOR (named numbers 0, 1, 2).
  - `circuit_rule`: no tag → None; upstream → None; same layer that isn't COMMAND → None; then same team → +, opposite → −.
  - Tested it on 9 cases until 9/9 passed. Before vs after: only 54 motor links changed sign; every sensor → command and command ↔ command sign stayed the same.
- Forward motors were still weak: AVB (forward command) reaches its motors mostly through pipes, which are tiny at `PIPE_K = 1`. Added one-way "circuit pipe" links: for each pipe between a command neuron and a motor on its own team, the parser also adds `command → motor, size × K` to `connections` (75 links).

## Experiments: getting the forward motors to fire (tail poke)
| Fix tried | Forward motors | Wrong side | Calms down? |
|---|---|---|---|
| Nothing (`PIPE_K = 1`) | 5 | 0 | ✅ |
| `PIPE_K = 3` everywhere | 77 | 317 | ❌ runaway |
| Cap each pipe package | 217+ | 420 | ❌ runaway |
| Stronger command ↔ motor pipes only (two-way) | 26 | 308 | ❌ motors push back up |
| **One-way command → motor links** | **54** | **1** | ✅ |
| One-way links for all downstream same-team pipes (incl. sensor → command) | 76 | 3 | ✅ but backward got even stronger (151) |

Picked the narrow one-way version. Backward motors still respond about 2x more than forward (144 vs 68 spikes), because AVA (backward command) has very dense chemical wiring to its motors. I left it: both directions are correct, and forcing them equal would be overfitting to one test. The robot readout can normalize per group instead.

## What I learned
- **Motor neurons are still neurons:** they take inputs (from commands) and send outputs (to muscles and to other motors). Muscles aren't in my model; the robot code will play that role.
- **Motor names:** D/V = dorsal or ventral muscles, A = backward, B = forward, the number = position along the body.
- **Data vs knowledge:** the table can't sign "complex" links, and no blanket guess works (tested +, −, and majority of tags). Known neuron jobs have to fill the gap.
- **Tags as data, one rule:** adding a sense later = adding rows to `CIRCUIT`, not new code. Same idea scales to the fly, where tags would come from a file.
- **Layer decides whether the rule speaks; team decides the sign.** Only downstream (and command ↔ command), so the rule never overrides the table for motor → motor (body wave) or creates upstream feedback loops.
- **Ping-pong needs a strong push in both directions.** One-way links are safe because the return path stays weak. Activity can still spread indirectly (motors firing more → more pushback), so the margin matters: about 240 vs the 256 threshold.
- **A function that reaches the end without `return` gives `None`**, which hid bugs in my first versions of `circuit_rule`.
- Order of checks matters: check "no tag" before comparing layers, or `None > 0` crashes.
- Save the file before Claude edits it, or the editor shows a save conflict (and "Overwrite" can undo the other edit).

## Mistakes I made (and fixed)
- First `circuit_rule` always returned + or −, so it would have overridden the table for every link in the brain (and crashed on two untagged neurons).
- Mixed up direction and sign: returned − for upstream links. Upstream should be None; − only means opposite teams.
- Forgot the same-team case at the end, so it fell off the end and returned None.

## Next steps
1. Motor readout: turn motor spikes into wheel direction + speed (normalize by group size).
2. 16-bit safety inside `neuron_model`.
3. Golden files for the full network, then the Verilog sim flow.


# bug-bot log: Oct 29, 2026 (part 3): wheels

## Summary
Built the robot readout: motor spikes → wheel direction and speed. **Head touch → wheels go backward, tail touch → wheels go forward, never the wrong way, and the robot stops on its own.** The whole chain (sensor → brain → motors → wheels) now works in Python.

## What I did
- The parser now exports `back_motors` (21 DA/VA indices) and `forward_motors` (18 DB/VB indices) into the generated file.
- Wrote the readout in `touch_test.ipynb` with two **muscle buckets**, one per direction. Each step, after the neurons update:
  1. leak both: `muscle = muscle - (muscle >> MUSCLE_LEAK)`
  2. add +1 for every motor in that group that fired
  3. decide: both below `STOP_BELOW` → stop; otherwise the bigger bucket wins
- My settings: `MUSCLE_LEAK = 2` (lose ¼ per step), `STOP_BELOW = 8`. Speed = the difference between the two buckets (like two opposing muscles: only the net pull moves the robot).
- Added a wheels panel to the plot (`plot_run(..., wheels=wheels)`): backward bars below the line, forward above.

## Result
| | Head poke | Tail poke |
|---|---|---|
| Wheels | backward, steps 10–31, no gaps | forward, steps 49–66 (one-step pause at the start) |
| Wrong direction | 0 steps | 0 steps |
| Top speed | ~51 | ~20 |

## Choosing the settings
| Leak | Coasts after motors stop | Problem |
|---|---|---|
| `>> 1` | ~5 steps | drops to 3 in the gaps, jerky |
| **`>> 2`** | **~11 steps** | middle ground |
| `>> 3` | ~22 steps | slow to start and slow to stop |

| Stop cutoff | Behavior |
|---|---|
| **8** | **smooth from the first burst, power of two (cheap check in hardware)** |
| 10 | ignores the first small burst |
| 16 | stops in the gaps again (jerky) |

## What I learned
- **Why a bucket:** motor neurons fire in bursts with gaps. Reading spikes directly makes the robot jerk. A leaky bucket works like a real muscle that stays tight for a moment.
- **Spikes, not voltages:** I thought about using the motor neurons' voltage as the memory. It dips exactly when the motors fire (reset to 0), creeps up on the wrong side without any spikes, and coasts too long. Spikes are also 1 bit, the neuron's real output.
- **+1 per motor:** the bucket counts how many motors fired (like counting people pushing a car). Weights are for neuron-to-neuron links, not for the readout.
- **Leak first, then add**, same as the neuron. Adding first leaks away the new spikes on the same step (step 10 gave 7 instead of 9).
- **Same leak for both buckets:** same rule, but each loses ¼ of its *own* value.
- **Steady state:** with `>> 2` a bucket settles at about 4 × (motors firing per step), so it tracks activity.
- **Integer shifts never reach 0:** `3 >> 2 = 0`, so the bucket gets stuck at 3. Stop has to be a cutoff, not "== 0". (Neurons do this too: 7 with `>> 3` stays 7.)
- **Powers of two are cheap in hardware:** `x < 16` is just "are the upper bits all 0?"
- `break` ends the whole simulation loop. "Stop" means the wheels stop, not the brain.

## Mistakes I made (and fixed)
- Left `back_motors = []` in the notebook, which replaced the imported lists with empty ones.
- Added the neuron's index to the bucket instead of its spike.
- Used one loop for both groups (21 vs 18 → would crash).
- Added before leaking.
- Used `break` for stop, which would have ended the run on step 0.
- Decided before counting, so the wheels were one step late.

## Next steps
1. 16-bit safety inside `neuron_model`.
2. Golden files for the full network.
3. Verilog sim flow.


# bug-bot log: Oct 29, 2026 (part 4): voltage floor

## Summary
Made the model 16-bit safe by adding a **voltage floor**: a neuron's voltage can never go below −512.

## Why
- The FPGA stores voltages in 16 bits (−32,768 to 32,767). Python has no limit, so it can't warn about overflow.
- The strongest possible brake in one step is RIAL at −4,270. Held there, a neuron would settle near 8 × −4,270 = −34,160, past the 16-bit limit. On the chip that wraps around to a big positive number and fires for no reason.
- Options: wrap (what raw hardware does, a bug), clamp at −32,768, or a floor. Picked a floor because real neurons have one too: inhibition pulls toward a fixed level, never past it. It's also cheap in hardware, and it stops brakes from lasting forever.

## What I did
- Added `FLOOR = -512` and an `elif v < FLOOR: v = FLOOR` in `neuron_model`, in **both** notebooks (`bug_bot.ipynb` is the 4-neuron test bench, `touch_test.ipynb` the real brain).
- Picked −512: a power of two, and below the −400 in my 4-neuron test, so the golden files don't change.

## Results
| Check | Result |
|---|---|
| 4-neuron golden files (all 6) | identical ✅ (lowest voltage −400) |
| Touch test lowest voltage | −512 (was −2,003) |
| Wheels | still backward on head (steps 10–34), forward on tail (50–66), 0 wrong way |
| Floors from −64 to −2,048 | almost no change in behavior |

## What I learned
- The top is already capped by firing (≥ 256 → reset to 0), so a floor at the bottom bounds the voltage completely: −512 to 255.
- `elif` is enough: a voltage can't be ≥ 256 and below −512 at the same time, so order doesn't matter.
- `bug_bot.ipynb` is my test bench: small known answers to check Verilog against. My current Verilog is hand-wired (one `lif_neuron` per neuron); the scalable core will first have to match these same 4-neuron golden files.
- `neuron_model` lives in two places, so every math change has to go into both.

## Next steps
1. Golden files for the full network.
2. Demo website (my model exports runs, Claude builds the visualizer).
3. Add the floor to `lif_neuron.v` during the Verilog step.


# bug-bot log: Oct 29, 2026 (part 5): full-network golden files

## Summary
Saved my 300-neuron head + tail run as golden files: the answer key my future scalable Verilog core has to match bit for bit. **The Python reference model is done** (motors, readout, floor, golden files).

## What I did
- Claude wrote `python/golden.py` (tooling). My notebook calls `save_golden(all_spikes, all_voltages, pokes, prefix="full")` in its own cell, so the files only get rewritten when I choose.
- Files in `data/`:

| File | Lines | Each line |
|---|---|---|
| `full_inputs.txt` | 80 | `head*2 + tail` (same as `chain_inputs.txt`) |
| `full_expected_spikes.txt` | 80 | 300-bit hex number, **bit i = neuron i** |
| `full_expected_v.txt` | 24,000 | one 16-bit voltage (`%04x`), line = `step * 300 + neuron` |

- The exporter reads the files back the way a testbench would and checks every spike and voltage. My files also matched Claude's independent run byte for byte.

## Decisions
- **Bit i = neuron i** for spikes (not "first neuron = top bit" like my chain file), because the scalable core will look up `spikes[i]`.
- **One voltage per line, 16 bits:** easy to read and debug. The golden files live on the computer only (~120 KB), not on the chip.

## What I learned
- Golden files are for the testbench in simulation. They never go onto the FPGA, so their size doesn't matter much.
- What goes **on** the chip: the network (~3,744 connections, 1,087 pipes), 300 voltages, and spike flags, about 110,000 bits total. That fits easily in small FPGAs (iCE40 UP5K, Artix-7).
- Thanks to the floor, a stored voltage is always −512 to 255, so it fits in **10 bits** instead of 16 (37% smaller). The math during an update still needs more bits. That's a hardware decision for later.
- `& 0xFFFF` turns a negative number into 16-bit two's complement: −512 → `fe00`.
- Restarting the kernel wipes all variables: run the simulation cell before the golden-file cell (or Run All).

## Next steps
1. Demo website: my model exports runs, Claude builds the visualizer. Preview privately, then GitHub Pages + a GIF in the README.
2. Senses: nose touch first.
3. Verilog: scalable core, matched against the 4-neuron and full-network golden files.


# bug-bot log: Oct 30 – Nov 1, 2026: scalable Verilog core runs the whole worm

## Summary
Built the time-multiplexed Verilog core piece by piece, each with a cocotb test. **`core.v` now runs the full 300-neuron worm and matches my Python golden files for all 80 steps**, every voltage and every spike. Each step takes about 2,100 ticks (~21 µs at 100 MHz); the robot only needs one step every 10 ms.

## What I did
| Piece | What it is |
|---|---|
| `lif_math.v` | the neuron update as pure math (only `assign`), tested on 27,648 cases |
| Memories | wiring loaded from `.mem` files with `$readmemh` (CSR for links and pokes, a flat list for pipes); `voltages`, `totals`, `spikes` zeroed at start |
| State machine | IDLE → CLEAR → POKES → SPIKES → PIPES → UPDATE → IDLE. `start_step` starts a step, `busy` says it's running |
| CLEAR / UPDATE | walk `neuron_index` over all neurons (`== N` means done) |
| POKES | two counters: which poke, and which link (`slot`); a poke is done when `slot == poke_start[poke_index + 1]` |
| SPIKES | the same pattern over neurons, with a **jump**: a neuron that didn't fire is skipped in one tick (quiet step: 912 ticks instead of ~4,650) |
| PIPES | one tick per pipe: flow + spike packages into `totals[a]` and `totals[b]` |

- Claude wrote the tooling: `python/make_mem.py` (the `.mem` files) and the tests (`test_core_memories/clear/pokes/spikes/pipes/golden`). I wrote all of `core.v`.

## Decisions
- **One spike list**, no double buffering: the jobs never overlap, and SPIKES and PIPES run before UPDATE overwrites `spikes`.
- **SPIKES jumps over silent neurons**, PIPES doesn't: flow runs whenever two voltages differ, so every pipe is visited every step.
- **`pipe_size` stays 8 bits unsigned in memory**; the extra 0 bit only exists in the math (`$signed({1'b0, size})`), so it's added once instead of stored 1,087 times.
- **Board: Arty A7-100T**, using Vivado on my Windows laptop (Vivado doesn't run on Mac). The Kria KV260 is probably better for the fly, but harder to start on.

## What I learned (my Verilog notes from building the core)

### 1. The big idea: time-multiplexing
- **One** neuron circuit (`lif_math`), placed once, always computing. A counter (`neuron_index`) picks which memory slot it reads; the `always` block saves its answer. Nothing is "called": the circuit just sits there, wired to whatever the counter points at.
- The circuit doesn't grow with the network, only the memories do. Same design for 4 neurons or 300 (or 140,000 for the fly): you load different memory files.
- Yosys schematic: ~178 parts for my core, and **137 of them are multiplexers** ("pick one" switches). Every `if/else` and every "which counter goes into this address" becomes one.

### 2. wire vs reg (the most important rule)
| | `reg` + `<=` (inside `always`) | `wire` + `assign` (outside `always`) |
|---|---|---|
| What it is | a box that **remembers** | a **formula** that's always live |
| New value shows up | at the **end** of the tick (next tick) | **instantly**, the same tick |
| Use for | things that must last: `voltages`, `totals`, counters, `state` | in-between math for right now: `pipe_flow`, spike packages, `lif_math` |
- **One `assign` per wire**, and a wire can never feed itself. That's why `lif_math` needs a new name per step (`temp_voltage_holder`, `voltage_after_reset`, ...). One formula, but its **value** changes whenever its inputs change.
- `assign` goes **outside** `always` (module level, next to the wires and module instances). Inside `always` you only use `<=`.
- A wire **reads** a counter, it never changes it. Only the `always` block writes regs, and each reg is written from only one `always` block. Reading can happen anywhere.
- Python picture: a wire is a little helper function that always uses the current loop variable; the `always` block is the loop, one pass per tick.
- A wire isn't storage, so extra in-between wires cost no memory. Without `[...]` a wire is 1 bit (`new_spike`); with `[15:0]` it's 16.
- A module's output has to drive a **wire**, not a memory slot directly.

### 3. How a tick works: the snapshot rule
- Each `posedge clk`: every `<=` line reads the values from the **start** of the tick (a snapshot), and all new values are saved together at the end. So one line can't see what another line just wrote that same tick.
- **Last `<=` wins:** if two lines set the same reg (or the same memory slot) in one tick, only the last one counts. That's how my package got wiped by the flow line, and how `neuron_index <= 0` got overwritten by `+ 1`.
- Different slots are fine: `totals[a]` and `totals[b]` can both be written in one tick (in simulation).
- Lines **after** the end of an `if/else if` chain aren't inside any branch: they run **every** tick of that state. Put the "done" check, the work, and the counter move in one chain so exactly one branch runs.
- `else` pairs with the nearest `if`. Separate `if`s can all run in the same tick; `if / else if / else` runs exactly one.
- `=` is for `initial` blocks; inside `always @(posedge clk)` use `<=`. `+=` is not a `<=`, write `x <= x + y`.

### 4. Memories
- Declared `reg [width-1:0] name [0:depth-1];`. The left brackets are **bits per slot**, the right ones are **how many slots**. `[0:0]` is one slot, fine; `[0:-1]` (zero slots) isn't, which is why the chain gets a do-nothing pipe.
- Write one slot per tick (`totals[i] <= 0`), never a whole memory at once.
- An `initial` block runs once at the start: `$readmemh({MEM_DIR, "/file.mem"}, memory)` loads hex, one line per slot, and a `for` loop zeros `voltages`, `totals`, `spikes`.
- `.mem` files are hex two's complement at the memory's width: in 11 bits, −400 → `670`, 300 → `12c`.
- Icarus deletes memories that nothing ever writes or loads.
- Real block RAM comes in fixed shapes (like 1K × 18 or 2K × 9), and the tools combine blocks automatically, so odd widths are fine. **Real BRAM answers a read one tick later** (two for a read inside a read): the main change for the board.

### 5. Module structure (mistakes I made in the first version)
- Parameters go in `#( ... )`, ports in `( ... )`; `localparam` goes in the body, not in `#()`. Memories aren't ports.
- `endmodule` is one word. No semicolons after each port inside the parentheses (commas).
- Parameters set sizes from outside (`N`, `N_LINKS`, `N_POKES`, `N_POKE_LINKS`, `N_PIPES`, `MEM_DIR`); the tests pass the worm's numbers, and the defaults are the chain's.
- Inputs nobody drives are `x`/`z` (unknown), not 0. A reg nobody gave a starting value is `x`, and `x == N` is never true, so the chip hangs. Give every counter a start value right before the job that uses it.
- Synchronous reset: `if (reset)` is the first check inside `always @(posedge clk)`.
- `===` only works in simulation; use `==` in real designs.

### 6. State machines
- `localparam IDLE = 0, CLEAR = 1, ...` plus a `state` reg. These are **numbers**, not bit positions: a 3-bit `state` holds 0–7, room for 8 states. The order of jobs comes from each job's `state <= NEXT`, not the numbers.
- Each tick, only the current state's branch runs. It's a Python `while` loop with `if/elif` on `state`.
- `start_step` (a one-tick pulse from outside) starts a step; `busy` is 1 while it runs. IDLE is most of the time: the robot taps `start_step` on a timer (like 100 steps/sec), so the step rate is a knob.
- My order: IDLE → CLEAR → POKES → SPIKES → PIPES → UPDATE → IDLE. SPIKES and PIPES must run **before** UPDATE, because UPDATE overwrites `spikes` (they need last step's) and `voltages` (pipes need start-of-step voltages). That's why one spike list is enough.
- `== N` style: a job over N things takes N + 1 ticks (the last tick just says "done").

### 7. Nested loops → two counters
- Hardware can't run a `for` inside a `for` in one tick, so it's rewritten as one loop doing **one small action per tick**, with two counters in one state:
  1. all done? → next state
  2. this one is off, or its range is used up? → next one (the jump)
  3. otherwise → do one link, `slot + 1`
- POKES: `poke_index` (which poke) + `slot` (which link). SPIKES: `neuron_index` (which sender) + `slot_spikes` (which link). Two counters because the outer one must **stay put** while the inner one walks.
- `pokes` is an **input port**, not memory: `pokes[poke_index]` is "is this poke touched right now", set from outside before `start_step`.

### 8. CSR (the wiring format)
- All senders' link lists glued into flat lists (`link_receiver`, `link_weight`), plus `start`, where `start[i]` is the **slot number** where sender i's links begin. Sender i owns slots `start[i]` to `start[i+1] - 1`, so `start` has **N + 1** entries (the last one is the end marker).
- One slot = one link (one receiver + its weight). A receiver can appear many times (once per sender that talks to it), and can point to any neuron, earlier or later. Only the **reading** order goes forward, grouped by sender.
- Start lists are grouped by **who sends**: `poke_start` per poke, `start` per neuron.
- `slot == start[neuron_index + 1]` means "this sender is done" (like Python's `range`, which stops before the end). A sender with no links is done instantly (`start[i] == start[i+1]`).
- Set `slot` once at the start of the job; after that it only moves forward (deliver: + 1, jump: to `start[neuron_index + 1]`).
- **Jumps** skip senders that didn't fire in one tick: a quiet worm step went from ~4,650 to 912 ticks.
- I rejected a bitmap (one bit per possible pair) because the worm is sparse: most pairs aren't connected.
- Pipes don't use CSR or jumps: flow runs whenever two voltages differ, so every pipe is visited every step, and a flat list with one counter is enough.

### 9. Bits, widths and counting
- A counter needs room for **one past the end**: `poke_index` must reach 2 (not 1-bit), the pipe counter must reach 1,087 (not 9-bit, max 511). Too small → it wraps to 0 like an odometer and loops forever.
- Bits needed: receivers 9 (neurons 0–299), weights 11 signed (−750..710), `start` 12 (up to 3,744), voltages stay −512..255.
- **Verilog does the math in the width of the result:** with a 16-bit `pipe_flow`, `391 × 100 = 39,100` overflowed before the shift. Worst case 767 × 250 = 191,750 needs 19 bits signed, so `pipe_flow` is 20.

### 10. Signed numbers
- Bits don't know they're negative; `signed` tells Verilog how to **read** them. `1111 1010` is 250 unsigned, −6 signed.
- **If any part of an expression is unsigned, the whole thing is unsigned**, even parts declared signed. Declaring the left side `signed` doesn't fix the right side.
- `>>>` keeps the sign (rounds down, like Python's `>>`); `>>` fills with 0s and turns negatives into big positives. `>>>` only acts signed on signed values.
- `$signed({1'b0, size})`: `{ }` glues bits together, `1'b0` is one 0 bit. The 0 on top keeps a size like 250 positive when read as signed. The extra bit lives only in the math circuit, not in all 1,087 memory slots (8 bits stored instead of 11).
- The **sign** of the flow comes from the voltage difference, the size is always positive.
- If a value can be negative, declare it `signed`.

### 11. Tools and the board
- Compile check: `iverilog -t null verilog/core.v verilog/lif_math.v`. "Unable to bind" = a name was never declared. "Not a valid l-value for a procedural assignment" = an `assign` (or a write to a wire) inside `always`.
- Tests: cocotb runs Icarus from Python. Each job's test checks `totals` first (where the mail went), then voltages and spikes; the golden test replays my notebook's files.
- Yosys + Graphviz / netlistsvg draw schematics. Fine for `lif_math`, spaghetti for `core`: that's why people draw block diagrams.
- Board: Arty A7-100T. Vivado runs on Windows/Linux, not macOS. On a real board there's no `print`: I'll need UART or Vivado's logic analyzer, a constraints file for the pins and clock, and the BRAM read delay.

## Mistakes fixed
- Counters never given a starting value (stuck at `x`), lines outside the `if/else` chain running every tick, the done check using `N` instead of `N_PIPES`, packages and flow held in regs (one tick late), the package including the neuron's whole total (counted it twice).

## Next steps
1. Muscle-bucket readout in Verilog (motor neurons → wheels).
2. Buy the Arty A7-100T; learn the BRAM read delay (reads take a tick) and adapt the jobs.
3. Later speed-ups: clear totals during UPDATE, a list of who fired, store weights ÷ 10 (all are multiples of 10, saves 3 bits per link).


# bug-bot log: Nov 4, 2026: first Vivado synthesis, and why `totals` didn't fit

## Summary
Ran the core through Vivado for the first time. It fit on the chip, but used 42% of the LUTs because `totals` was built out of flip-flops instead of a RAM. The cause is that PIPES wrote `totals` twice in one tick. Split PIPES into two ticks per pipe (Fix 1). All tests still pass and the full worm still matches the golden files. Fix 2 (one write line for `totals`) is next, and I haven't rerun synthesis yet.

## What I did
- Ran Vivado 2026.1 synthesis on the Windows laptop (synthesis only, no clock constraint) for `core.v` + `lif_math.v`, part `xc7a100tcsg324-1` (Arty A7-100T), full-worm parameters. All 8 cocotb tests also pass on Windows (Icarus 12).
- Result: 0 errors, 0 critical warnings, 1 warning, all 9 `.mem` files read.

| Resource | Used |
|---|---|
| LUTs | 26,381 (42%) |
| LUT as distributed RAM | 290 |
| Flip-flops | 5,021 (4%) |
| BRAM tiles | 4 (2 RAMB36 + 4 RAMB18) |
| DSP | 1 (`pipe_flow`'s multiply) |

- The warning: `[Synth 8-4767] Trying to implement RAM 'totals_reg' in registers`, pointing at `core.v:175`. Reason 1: "RAM has multiple writes via different ports in same process". Reasons 2–6: "Invalid write to RAM". Reason 7: "No valid clock found for write to RAM".

| Memory | Vivado built it as |
|---|---|
| `link_receiver`, `link_weight`, `pipe_a`, `pipe_b`, `pipe_size` | Block RAM |
| `start` | LUT ROM |
| `voltages`, `spikes` | LUT RAM |
| `totals` | 4,800 flip-flops + big selectors |

- Fix 1: added a one-bit reg, `flipflopper`, so each pipe takes two ticks: side a, then side b. `neuron_index` only moves on after side b.

## Decisions
- **My first idea:** a one-bit "read or write" signal. Read and do the math on one tick, save the result in a reg, write it on the next tick. This doesn't fix pipes alone, because both writes still land on the same write tick. To work, it would need four ticks (read a, write a, read b, write b), so two bits.
- **What I did instead:** kept one bit, but made it mean "side a or side b". LUT RAM reads are instant, so a separate read tick isn't needed yet.
- **Keeping the read/write idea for later:** BRAM answers one tick late, so the jobs will need a read tick at the BRAM stage. A BRAM read tick can only send the address, because the value isn't there yet, so the math happens on the next tick.
- Two ticks per pipe costs 1,087 extra ticks per step: about 2,100 → 3,200 ticks, or 21 → 32 µs at 100 MHz. That's fine for the worm.
- Doing it in two ticks doesn't change the math: `voltages` and `spikes` don't change during PIPES, additions can go in any order, and no pipe connects a neuron to itself. The golden files still match.

## What I learned

### 1. What's on the chip
| | Job | Think of it as | Read speed | Arty A7-100T has |
|---|---|---|---|---|
| LUT | Logic | A tiny list of pre-written answers | Instant | ~63,400 |
| Flip-flop | Remembers 1 bit | A sticky note | Instant | ~126,800 |
| BRAM | Stores lots of data | A filing cabinet | One tick later | 135 blocks (36 Kbit each, ~4.9 Mbit) |

- **LUT:** it doesn't calculate, it looks up. AND is just `answers = [0, 0, 0, 1]` and `out = answers[a*2 + b]`. Each LUT on this chip has 6 inputs, so 64 stored answers. Change the answers and it does a different job.
- **LUT RAM (distributed RAM):** using a LUT's 64 answers as a tiny memory. Instant reads, one write per tick. Great for small memories, wasteful for big ones.
- **On a chip, every branch is real circuitry.** It takes up space even when it isn't used.

### 2. Why two writes in one tick break a RAM
- A RAM's write door is a real bundle of wires, one for the address and one for the data. A wire carries one number at a time. With a pipe between neurons 12 and 57, the address wires would have to say 12 and 57 at once.
- Python runs two lines one after the other. In an `always` block, both happen on the same tick.
- Flip-flops can do it because each one has its own wires. That's why Vivado fell back to them.

| Memory | Doors | One pipe in one tick needs | Fits? |
|---|---|---|---|
| LUT RAM | 1 write door + instant reads | 2 writes | No |
| BRAM | 2 doors, shared by reads and writes | 2 reads + 2 writes = 4 | No |

- BRAM could do two writes in one tick. The problem is the reads each pipe needs as well, which makes four accesses.

### 3. Why it cost 42% of the LUTs
- 300 neurons × 16 bits = 4,800 flip-flops, which is 96% of all 5,021.
- As a RAM, `totals[i]` is one lookup. As flip-flops, it's like 300 separate variables and an `if/elif` chain with 300 branches, for all 16 bits, repeated everywhere the code reads `totals`. Those selectors are probably most of the 26,381 LUTs.
- For comparison, `voltages` and `spikes` together use 290 LUTs of RAM.

### 4. Which lines caused it
- `core.v` lines 174–175 (before the fix) were the definite cause: two writes to two different addresses on one tick.
- `totals` is also written from five separate lines (110, 126, 152, 174, 175), each with a different address. `voltages` has one (line 193). Each of those other lines only writes once per tick, so they never collide, but they may still be why Vivado says "Invalid write". The full log would show which line each reason refers to.
- Line 77 reads `totals[neuron_index]` instantly. That doesn't cause this warning, but it would keep `totals` out of BRAM later.

### 5. Regs and wires don't lose values
- Every `<=` updates at the same clock edge. The `assign` wires then recalculate during the tick, and the next edge uses the results. Nothing gets lost in that handoff.
- But a wire always shows its current inputs. `pipe_flow` depends on `neuron_index`, so `neuron_index` has to stay put for both sides of a pipe.

### 6. A passing test can prove less than it looks like
- The chain golden test passed while pipes were broken, because the chain's only pipe has size 0, so it adds nothing. `test_core_pipes` and the full golden test caught it.

### 7. Yosys isn't Vivado
- Yosys turns `link_receiver` into plain registers, but Vivado put it in BRAM by merging the address registers into it (`_reg_rep` in the log). Different tools make different choices, so check the real one.

## Mistakes fixed
- Left `neuron_index <= neuron_index + 1` outside the new `if/else`, so it ran every tick and moved on after side a. Half the pipe writes were skipped: pipe 0 side a, pipe 1 side b, pipe 2 side a, and so on. `test_core_pipes` failed (`totals[1]` was 300, should be 400) and the full golden test failed at step 1 (4 neurons differ, e.g. PVR (#129): 67, should be 70). Moving the line so it only runs on side b fixed it. This is the same mistake as before: a line outside the `if/else` runs every tick.

## Next steps
1. Fix 2: one write line for `totals`, fed by wires that pick the address and value for each state. Watch out for: copying the exact `if` conditions (some ticks write nothing), using wires rather than `<=` for the write signals (or the write comes a tick late and a second link to the same neuron loses the first), and resetting anything new.
2. Rerun synthesis. The warning should go away and flip-flops should drop to a few hundred.
3. Add a 100 MHz clock constraint. Without one, synthesis says nothing about speed.
4. Update `CLAUDE.md`: ticks per step, and the note that says `link_receiver` becomes registers.


# bug-bot log: Nov 4, 2026 (later): synthesis rerun after Fix 1, `totals` fits

## Summary
Reran Vivado synthesis with the two-tick PIPES change (Fix 1). The `totals` warning is gone and the core shrank from 42% of the LUTs to 2.4%. `totals` is now LUT RAM, like `voltages` and `spikes`. Fix 1 alone was enough for the worm, so Fix 2 and the BRAM read timing move to the fly stage.

## What I did
- Pulled the Fix 1 commit onto the Windows laptop and ran all 7 core tests (Icarus 12): all pass. The full golden run went from 1,702,725 ns to 2,572,325 ns: exactly 1,087 extra ticks per step, one per pipe (~21 → ~32 µs per step).
- Reran synthesis in the same Vivado project (same part and full-worm parameters). All 9 `.mem` files read.

| Resource | Before Fix 1 | After Fix 1 |
|---|---|---|
| Warnings | 1 (`totals_reg` in registers) | **0** |
| LUTs | 26,381 (42%) | **1,545 (2.4%)** |
| LUT as memory | 290 | 912 |
| Flip-flops | 5,021 | **54** |
| F7 / F8 muxes | 2,616 / 1,168 | 169 / 0 |
| BRAM tiles | 4 | 4 |
| DSP | 1 | 1 |

| Memory | Before Fix 1 | After Fix 1 |
|---|---|---|
| `link_receiver`, `link_weight`, `pipe_a`, `pipe_b`, `pipe_size` | BRAM | BRAM |
| `start` | LUT ROM | LUT ROM |
| `voltages`, `spikes` | LUT RAM | LUT RAM |
| `totals` | 4,800 flip-flops + selectors | **LUT RAM** |

- Updated `CLAUDE.md`: ticks per step, PIPES two ticks per pipe, synthesis results, the Yosys/BRAM note, the Windows setup, and the roadmap.

## Decisions
- **Fix 2 (one write line for `totals`) is not needed for the worm.** Vivado accepted the five separate write lines once no tick wrote twice. Keeping it for the fly, where `totals` has to be BRAM.
- **BRAM read timing (ask-then-use) moves to the fly stage.** The worm's state fits in LUT RAM, which reads instantly, and the wiring tables already reach BRAM through the merged address registers. So the worm needs no read-tick changes for the board.
- Fly sizes, for later: fly `totals` alone is 140,000 × 16 bits ≈ 2.2 Mbit, but the Arty has only ~1.2 Mbit of LUT RAM in total (and ~4.9 Mbit of BRAM). So the fly needs BRAM for its state, and DDR for its wiring.

## What I learned

### 1. Three kinds of storage, not two
| | Read | Writes per tick | Good for |
|---|---|---|---|
| Flip-flops (sticky notes) | Instant | Any number | A few values; costly for lists |
| LUT RAM (small drawers) | Instant | 1 | Small lists (the worm's 300 neurons) |
| BRAM (filing cabinet) | One tick later | 2 doors, shared by reads and writes | Big lists (the fly) |

- Fix 1 made `totals` legal for LUT RAM (one write per tick). It still isn't legal for BRAM, because each tick reads and writes back in the same tick, and BRAM's answer comes a tick late. Vivado picks the cheapest storage that's legal, so it chose LUT RAM.

### 2. The flip-flops were what cost the LUTs
- Removing 4,800 flip-flops also removed ~25,000 LUTs. Those were the 300-way selectors needed to read and write a flip-flop array at a changing address. As RAM, a read is one lookup.
- LUT as memory went up (290 → 912) because `totals` is read at several different addresses (the neuron being updated, link receivers, pipe sides a and b), and LUT RAM makes a copy for each read address. Still far cheaper than flip-flops.

### 3. Predictions were wrong in a good way
- The last log predicted flip-flops would drop to "a few hundred" after Fix 2. They dropped to 54 after Fix 1 alone.
- Claude predicted the warning might stay (read and write in one tick). That's true for BRAM, but Vivado used LUT RAM instead. Run the tool, don't guess.

### 4. `#1` is not a way to wait
- `#1` only exists in simulation; Vivado ignores it. Waiting a tick in hardware means a reg that remembers where you are (like `flipflopper` or `state`) and doing the next part on the next tick. A value written with `<=` is ready on the next tick.

### 5. Timing: think of a bell
- The clock is a **bell** that rings over and over. One bell to the next is one **tick**. All the work between two bells has to finish before the next one, because that's when the answer gets saved. If it isn't done, the chip saves a wrong number.
- **100 MHz means the bell rings every 10 ns**, so each tick gets 10 ns.
- A tick isn't a step. One **step** (one full update of the worm) takes ~3,200 ticks, or ~32 µs at 100 MHz. Each tick does one small item from that step's to-do list.

| Job in one step | Ticks |
|---|---|
| CLEAR | ~300 |
| POKES | A few |
| SPIKES | ~300 and up, depending on who fired |
| PIPES | ~2,174 |
| UPDATE | ~300 |

- All ticks are the same length, so **the slowest tick sets the speed for all of them**, even the easy ones. If one tick needs 13 ns, every tick has to be at least 13 ns long.

### 6. The clock constraint
- It's one line in an `.xdc` file that tells Vivado how long a tick is: `create_clock -period 10 [get_ports clk]`. Without it, Vivado has no target, so the report has no slack for my clock.
- **Slack** is the time left over on the slowest path. Positive means it fits, negative means it's too slow. It's shown as WNS in Report Timing Summary.
- Top speed in MHz = 1000 ÷ (10 − WNS), when the period is 10 ns:

| WNS | Slowest path | Top speed |
|---|---|---|
| +2 ns | 8 ns | 125 MHz |
| 0 ns | 10 ns | 100 MHz |
| −3 ns | 13 ns | ~77 MHz |

### 7. Synthesis vs implementation
- **Synthesis** turns my Verilog into LUTs, RAMs and registers. Its timing is an estimate, because it doesn't know the wire lengths yet.
- **Implementation** places everything on the chip and connects it, so now it knows where every wire goes. Wires take time too, so this is the number that counts.
- **Run Implementation** reruns synthesis first if it's out of date.
- I don't need the board for this. Vivado calculates the times from its data about the chip, using worst-case numbers.

### 8. "Sub-optimal timing" means take the number from a desk, not the cabinet
- Vivado printed `INFO` messages saying the BRAM timing "might be sub-optimal". They aren't errors, and nothing is broken.
- BRAM is a slow filing cabinet. If I grab a number straight from it, the walk uses up part of the tick and leaves less time for the math. With made-up numbers:

```
bell ──── walk to the cabinet (3) ──── math (7 left) ──── bell
```

- BRAM has an optional extra register at its exit, like a desk the cabinet can put the number on. The math then gets the whole tick, but the read takes one more tick:

```
bell ──── cabinet puts the number on the desk ──── bell
bell ──── math (the full 10) ──────────────────── bell
```

- My code uses the BRAM value straight away, so Vivado has no register to merge in there. The message is saying it works, but could be faster with a desk.

### 9. How to go faster (for later)
- What I really want to shrink is **time per step = ticks per step × time per tick**.
- **Shorter ticks:** split a long path with registers, like doing the multiply on one tick and the add on the next.
- **Fewer ticks:** skip work, like clearing `totals` during UPDATE (saves up to 300 ticks).
- More MHz doesn't always mean a faster step, because splitting adds ticks. If PIPES went from 2 to 4 ticks per pipe at 200 MHz: ~3,200 ticks × 10 ns = ~32 µs becomes ~5,400 ticks × 5 ns = ~27 µs. Twice the clock speed, but only about 16% faster.
- **Pipelining** gets around that, and has nothing to do with my neuron pipes. It's like laundry: the washer can start a new load while the last one is in the dryer. Each pipe still goes through several stages, but a new one could start every tick.
- PIPES is about two-thirds of the ticks in a step, so it's the best place to start. Measure first, so I work on the path that's actually slowest.

### 10. Timing rundown (everything in one place, with my real numbers)

**The bell.** The chip has a clock that works like a bell. One bell to the next is one tick. Between two bells, a value leaves a register, runs through logic, and has to reach the next register. When the bell rings, whatever has arrived gets saved. If the work isn't done, a wrong number gets saved.

**MHz and ns.** These describe the same bell: MHz is how often it rings, and ns is the time between rings. MHz means "million times per second", and a ns is one billionth of a second. To convert, ns = 1000 ÷ MHz. More MHz means more ticks per second, but less time for each one.

| Speed | Time per tick |
|---|---|
| 50 MHz | 20 ns |
| 100 MHz | 10 ns |
| 200 MHz | 5 ns |

**Tick vs step.** A tick does one small item, and a step is one full update of the worm, a to-do list of about 3,200 ticks.

**The slowest tick sets the speed.** All ticks are the same length, so one slow tick slows down all of them.

**The constraint is a note, not a control.** `create_clock -period 10` tells Vivado how often the bell rings, and Vivado checks whether everything fits. It doesn't change the real clock, which is a physical part on the board. If the `.xdc` said 20 ns but the real clock stayed at 100 MHz, the report would pass and the chip would still save wrong numbers, like planning for 20 minutes in an exam that ends at 10. To really run at 20 ns, I'd need a circuit that makes a 50 MHz clock, and then the note would be true.

**Synthesis vs implementation.** Synthesis turns Verilog into chip parts and can only estimate timing. Implementation places and wires them, so that's the number that counts. Wires take time too. I don't need the board for this.

**Reading the report.** WNS is the time left on the slowest path. Positive means it fits, negative means it's too slow. Mine was **−6.728 ns** at 100 MHz, with 1,346 of 7,666 endpoints failing. So my slowest path needs 10 + 6.7 = 16.7 ns, and my top speed is 1000 ÷ 16.7, or about **60 MHz** (~53 µs per step).

**My slowest path.** All of this happens in one PIPES tick (`pipe_flow`, then the write into `totals`):

```
bell → read pipe_a/b → read voltages → subtract + multiply → add to totals → bell
         3.87 ns          2.75 ns          5.59 ns             3.43 ns
```

That's 15.64 ns, plus 1.09 ns of fixed costs, for 16.73 ns in total. Wires are 41% of it, and the multiplier (the DSP) alone takes 5.07 ns.

**How to go faster.** Time per step = ticks per step × time per tick. I can make ticks shorter (cut long work across more ticks, saving values in regs at each cut) or use fewer ticks (skip work I don't need). Every extra tick in PIPES gets paid 1,087 times per step, so splitting everything stops helping. The tick also can't get shorter than its slowest remaining piece. The last two rows are estimates:

| Ticks per pipe | Ticks per step | Slowest tick | Time per step |
|---|---|---|---|
| 2 (now) | ~3,200 | 16.7 ns | ~53 µs |
| 3 (my cut) | ~4,300 | 10–11 ns | ~43–48 µs |
| 6 (every stage) | ~7,500 | 6–11 ns | ~45–83 µs |

**Why it matters for the fly.** 10 ns is tiny, but it gets multiplied by the number of ticks. Rough numbers, assuming ~10 million links and 10–100% of neurons firing in a step:

| | Worm | Fly (rough) |
|---|---|---|
| Ticks per step | ~3,200 | ~1–10 million |
| Time per step at 10 ns | 32 µs | 10–100 ms |
| Time per step at 20 ns | 64 µs | 20–200 ms |

For the worm, a slower clock wouldn't matter: over 15,000 steps per second is plenty. For the fly, it decides whether a drone can react in time. The wiring also won't fit in BRAM (roughly 200 Mbit vs 4.9 Mbit), so it would live in slower DDR memory, and the fly will need to do lots of work per tick, not just run a faster clock.

**The debugging loop.**
1. Run implementation.
2. Read WNS and the slowest path.
3. Find the biggest chunk and decide where to cut it.
4. Change the Verilog and run the tests.
5. Repeat until I hit my target or the gains stop being worth it.

**My plan for the next cut.** Three ticks per pipe: subtract on tick 1 (saving the difference and `pipe_size` in regs), then multiply and add to side a on tick 2, and to side b on tick 3. `pipe_size` has to be saved too, because reading it straight from BRAM on tick 2 would put the slow read back in that tick. After this, the next slowest path is probably the ~11 ns one from `link_receiver` or `pipe_a` BRAM → read `totals` → add → write `totals`.

## Mistakes fixed
- None this time. All tests passed on the first run.

## Next steps
1. Muscle-bucket readout in Verilog (motor neurons → wheels).
2. Add a 100 MHz clock constraint (a small `.xdc`) to see whether the core is fast enough. Synthesis alone says nothing about speed.
3. Maybe a Tcl script that rebuilds the Vivado project in one command, so the project folder doesn't have to be remembered or copied.
4. Fly stage, later: ask-then-use reads and one write line for `totals`, so the state can live in BRAM.

# bug-bot log: Nov 8, 2026: muscle readout in Verilog

## Summary
The core now turns motor neuron spikes into wheel commands, like the Python readout in `touch_test.ipynb`. `test_core_muscles` passes for all 80 steps of the head + tail run, and all the other core tests still pass (chain and full golden, memories, clear, pokes, spikes, pipes).

## What I did
- Loaded `motor_role.mem` (made last session by `make_mem.py`) into a new memory: `reg [1:0] motor_role [0:N-1]`, one entry per neuron (0 = not a motor, 1 = backward DA/VA, 2 = forward DB/VB).
- Added 4 outputs: `back_muscle`, `forward_muscle` (7 bits each), `wheel_direction` (2 bits: 0 stop, 1 backward, 2 forward) and `wheel_speed` (7 bits). All 4 are set to 0 in `reset`.
- Added parameters `MUSCLE_LEAK_FACTOR = 2` and `STOP_BELOW = 8`.
- Added two states, so a step now goes:

```
IDLE → CLEAR → POKES → SPIKES → PIPES → MUSCLE_LEAK → UPDATE → MUSCLE_UPDATE → IDLE
```

| State | Runs | Job |
|---|---|---|
| `MUSCLE_LEAK` | once per step, before UPDATE | `bucket = bucket - (bucket >> 2)` for both buckets |
| `UPDATE_SAVE` | once per neuron | if this neuron is a motor and `new_spike` is 1, +1 to its bucket |
| `MUSCLE_UPDATE` | once per step, after UPDATE | stop / backward / forward and the speed, then `busy <= 0` |

Two extra ticks per step, on top of ~4,600.

## Decisions
- **A role per neuron (`motor_role`), not a list of motor numbers.** Python asks "is this neuron in `back_motors`?", but `in` is a hidden loop. In hardware that means either 39 comparators in one tick (slow) or 39 ticks per neuron (~11,700 extra ticks per step). With `motor_role[neuron_index]` it's one lookup, like `start` in SPIKES.
- **Leak and decide get their own states.** They can't share one: the leak must come before the first +1, and the decide step after the last one. Both are small 7-bit math, so they shouldn't become the slowest path.
- **The buckets are outputs only for testing.** The robot only needs direction and speed. The test checks the buckets first, so a wrong answer shows whether the bug is in the buckets or in the decide logic. On the board, any output that isn't connected to a pin doesn't cost a pin.
- **Unsigned, 7 bits.** A bucket never goes negative and tops out at 87 (all 21 backward motors firing every step), and speed is at most 87 too. Signed 7 bits would only reach 63.

## What I learned
1. **Outputs vs peeking.** The ports are what the outside world (the robot) sees. `spikes` and `voltages` aren't outputs, but the golden test still checks them by looking inside the module, which only works in simulation. `output reg` is still a normal reg inside the module.
2. **`X + 1 = X`.** A reg that's never set is unknown, and adding to it keeps it unknown. It needs a starting value in `reset`.
3. **`<=` writes at the end of the tick.** In `UPDATE_SAVE`, `spikes[neuron_index]` still holds last step's spike during that tick, because `spikes[neuron_index] <= new_spike` hasn't happened yet. This step's spike is `new_spike`.
4. **Once per step vs once per neuron.** UPDATE runs 300 times per step, so a leak there would happen 300 times (20 → 15 → 12 → … → stuck at 3).
5. **The number in the error message tells you the bug.** At step 10, 9 backward motors fired and the chip showed 7 instead of 9: 0 + 9 = 9, then 9 − (9 >> 2) = 7. That's add-then-leak, so the leak was in the wrong place.
6. **Careful with brackets:** `motor_role[neuron_index] == 1` checks this neuron's role, while `motor_role[neuron_index == 1]` compiles fine but looks up neuron 0 or 1.

## Mistakes fixed
- `;` after the last parameter (the list uses commas, and nothing after the last item).
- Two things named `MUSCLE_LEAK` (a parameter and a state). Renamed the parameter to `MUSCLE_LEAK_FACTOR`.
- Buckets were `X` until reset set them to 0.
- Used `spikes[neuron_index]` (last step's) instead of `new_spike` (this step's): the chip added 0 at step 10 instead of 9.
- The leak state ran after UPDATE: the chip showed 7 instead of 9. Moved it between PIPES and UPDATE.
- Checked the tie rule by hand, since the test never has a tie at 8 or above: `>` (not `>=`) sends a tie to forward, same as Python.

## Next steps
1. Vivado (Windows): `git pull`, `reset_run synth_1`, then implementation, to check the new states didn't make timing worse (WNS −0.93 ns at 100 MHz).
2. Close 100 MHz timing (worst path: SPIKES `start` lookup → `totals`).
3. Basys 3 top file: connect `wheel_direction` and `wheel_speed` to pins (maybe the buckets to LEDs), and touch inputs to pokes.

# bug-bot log: Nov 8–9, 2026 (later): Vivado run 8, blinky, and the board top file

## Summary
Checked the muscle readout in Vivado (run 8), got a first board test (blinky) ready, and wrote the top file that connects the worm core to the Basys 3's buttons and LEDs. `test_top` passes all 80 steps in simulation. The board itself isn't working yet: Windows doesn't see its USB data link, most likely because of the cable.

## What I did
- **Vivado run 8** (Basys 3, with the muscle readout):

| | Run 7 | Run 8 |
|---|---|---|
| WNS | −0.93 ns | −0.74 ns (~93 MHz max) |
| Failing endpoints | 366 | 244 |
| Worst path | SPIKES `start` lookup → `totals` | same |
| LUTs | 1,571 | 1,602 |
| Flip-flops | 156 | 172 |
| Pins | 6 | 29 |

  The muscle states didn't make a new worst path. The small WNS gain is probably placement luck, since that path didn't change. Open puzzle: the new regs are 23 bits, but only 16 flip-flops were added.
- **Blinky** (`verilog/blinky.v`, `blinky.xdc`): LED 0 blinks once per second, LED 1 follows the center button. Simulated with the half second shrunk to 4 ticks and looked at it in Surfer. Built the bitstream on Windows.
- **Board connection failed:** Hardware Manager only showed `localhost`, and Device Manager showed no "USB Serial Converter A/B". The board only powers on sometimes. Since the board gets its power over the same cable, power working but data not points to a charge-only or broken cable (power uses the outer wires, data the middle two).
- **Top file** (`verilog/top.v`), simulated by `verilog/test_top.py`:
  1. Button sync: each button goes through two flip-flops before use.
  2. Step timer: counts to `STEP_TICKS`, then `start_step` is 1 for exactly one tick. `heartbeat` flips each step so I can see the timer on an LED.
  3. `core` inside `top`, with `pokes = {tail, head}`.
  4. LEDs: 15 backward, 14 forward, 13 heartbeat, 12/11 head/tail button, 6–0 wheel speed in binary.
- **`board.v` + `board.xdc`**: makes 50 MHz from the board's 100 MHz with Vivado's Clocking Wizard (`clk_wiz_0`) and holds `top` in reset until that clock is steady (`btnC | ~locked`). Vivado only, not built yet.
- `test_top` holds the head/tail buttons like `full_inputs.txt`, checks the LEDs every step against the Python rules, and fails if `start_step` ever comes while the core is `busy`. Passes all 80 steps in ~8 s.

## Decisions
- **Run the board at 50 MHz** instead of closing 100 MHz timing first. The core needs ~10.7 ns per tick, and 50 MHz gives 20 ns. 100 MHz timing becomes "nice to have later".
- **One clock for everything** in `top` (timer, buttons, core). A 1-tick pulse on a 100 MHz clock could fall between two 50 MHz edges and get missed.
- **`STEP_TICKS = 5,000,000`** (0.1 s at 50 MHz, 10 steps/s), so the backward response lasts ~2.5 s and I can watch it. The minimum is the longest possible step, ~8,200 ticks if every neuron fired. Too small, and steps get skipped with no error, because the core only listens for `start_step` in IDLE.
- **No debouncing:** a few ms of button flicker doesn't matter when steps are 100 ms apart.
- **Separate Vivado projects:** `bug-bot-synth` (core only, for timing work), `blinky`, and `bug-bot-board`.

## What I learned
1. **Simulate first, then the board.** On the board I can only see LEDs. In simulation I can see every signal. The cable only blocks the last step.
2. **Reading waveforms:** a waveform is a table turned sideways. Click a moment, then read the value column next to the names. Multi-bit signals show as a number (`led [1:0] = 3` means both on). Come with one question instead of reading everything.
3. **A reg holds its value until assigned.** Blinky's LED depends on how many times the counter has wrapped, not on the counter's current value.
4. **The clock never slows down.** The timer decides when a step starts, and the core waits in IDLE the rest of the time (~4,500 ticks of work, then ~4,995,000 of waiting).
5. **Buttons aren't in sync with the clock**, so they go through two flip-flops first (2 ticks of delay).
6. **Debug LEDs:** a 1-tick pulse is invisible to a human, so `heartbeat` holds for a whole step. Each LED answers one question when the board does nothing.

## Mistakes fixed
- None in the RTL this time. Board trouble was the USB cable, not the design.

## Next steps
1. Vivado project `bug-bot-board` (`core.v`, `lif_math.v`, `top.v`, `board.v`, `board.xdc`, Clocking Wizard at 50 MHz): build the bitstream and check timing passes at 50 MHz.
2. Get a data micro-USB cable, then program blinky, then the worm: hold the up button ~1 s and LED 15 should light for ~2.5 s.
3. Optional: follow one head press in Surfer (`verilog/sim_build/top/top.fst`).
4. Later: 100 MHz timing, the robot (motors instead of LEDs), then learning (R-STDP).

# bug-bot log: Nov 9, 2026: board panel on the website, first full-worm bitstream (Vivado runs 9 and 10)

## Summary
Added a simulated FPGA board to the demo website, built the whole board design in Vivado for the first time (run 9), fixed its one critical warning, and rebuilt it clean (run 10). The bitstream for the Basys 3 is done and timing passes at 50 MHz. The only thing left before the worm runs on the real board is a data USB cable.

## What I did
- **Website board panel** (`docs/index.html`): a 16-LED Basys 3 panel next to the robot in the hero. The LEDs come from the **Verilog simulation** (`docs/board.json`, written by `test_top.py` when it passes), not the Python model. Speed LEDs light in the direction's color with their bit weights under them ("speed 36 = 32 + 4"). The ▲ / ▼ buttons play the head / tail poke, ● restarts the demo, and the header shows how many ticks the chip took that step (~4,500 ticks ≈ 90 µs at 50 MHz). Also updated the "Built to run on an FPGA" section and the roadmap.
- **New Vivado project `bug-bot-board`** (`C:\fpga\vivado\bug-bot-board`): `core.v`, `lif_math.v`, `top.v`, `board.v` + `board.xdc`, part `xc7a35tcpg236-1`, top = `board`, generic `MEM_DIR` only (the worm sizes are already `top.v`'s defaults). Made `clk_wiz_0` with the Clocking Wizard: 100 MHz in, 50 MHz out, reset + locked, synthesized out of context (built once and reused).
- **Run 9** (first full board build): bitstream written, all 10 `.mem` files read, timing met, but **1 critical warning (TIMING-6)**: the 100 MHz clock was declared twice.
- **Fixed `board.xdc`:** removed its `create_clock` line, because the Clocking Wizard's own constraints already declare that clock.
- **Run 10** (rebuild after the fix): 0 critical warnings, one 100 MHz and one 50 MHz clock. Committed the bitstream (`logs/vivado/impl_2026-11-09_run10_board.bit`) so any computer with Vivado can program the board without rebuilding.

| | Run 8 (core alone, 100 MHz) | Run 9 (board, 50 MHz) | Run 10 (board, clock fix) |
|---|---|---|---|
| WNS | −0.74 ns ❌ | +6.61 ns ✅ | +6.21 ns ✅ |
| Critical warnings | 0 | 1 (TIMING-6) | **0** |
| LUTs | 1,602 | 1,611 | 1,611 |
| Flip-flops | 172 | 211 | 211 |
| BRAM tiles / DSPs | 4 / 1 | 4 / 1 | 4 / 1 |
| Clock maker (MMCM) | – | 1 of 5 | 1 of 5 |
| Pins | 29 | 20 | 20 |

  Pins went down because they're real now: 1 clock + 3 buttons + 16 LEDs. Before, every core output counted as a pin. The +39 flip-flops are mostly the 23-bit `step_count` and the 6 button sync flip-flops. Worst path (runs 9 and 10): still SPIKES, `slot_spikes` → add weight → write `totals`, 13.3 ns, ~73% of it wire (~75 MHz max). Power 0.195 W.
- Leftover warnings, all expected: `led[10:7]` driven by constant 0 (unused on purpose), "not ideal for floorplanning" (only matters for hand placement), and SYNTH-5/6 (memories put in LUT RAM, which is what I want for `voltages`, `spikes`, `totals`).

## Decisions
- **Website LEDs come from the Verilog simulation**, not Python, so the panel shows what the chip design actually does. `board.json` has to be regenerated (rerun `test_top.py`) whenever `core.v` or `top.v` changes.
- **The Clocking Wizard owns the clock constraint.** `board.xdc` only sets the pin (W5).
- **Commit a `.bit` only when it's one I actually load onto the board.** It's 2.2 MB, and git keeps every version forever.

## What I learned
1. **Out of context IP:** Vivado builds the clock maker once on its own (`clk_wiz_0_synth_1` under "Out-of-Context Module Runs") and reuses it, so rebuilding my design doesn't rebuild the clock maker.
2. **Declaring one clock twice is a real problem for the tool, even if not for the board.** Vivado thought there were two unrelated 100 MHz clocks, timed every path twice, and couldn't prove they were in step (TIMING-6). One clock, one `create_clock`.
3. **Vivado only works as hard as the clock needs.** The worst path got slower (10.7 → 13.3 ns) because with 20 ns per tick it stops trying once timing passes and places things more loosely. Same logic, longer wires. WNS also moves a bit between builds (6.61 → 6.21) with no logic change.
4. **Fewer pins once there's a real top.** Pins are only what leaves the chip, so the core's outputs no longer count once `top` turns them into 16 LEDs.
5. **Git paths are relative to where the terminal is.** After `cd docs` for the website preview, `git add docs/index.html` failed ("did not match any files"); `cd ..` back to the repo root fixed it. `pwd` shows where I am.

## Mistakes fixed
- `board.xdc` declared the 100 MHz clock a second time (TIMING-6 critical warning in run 9). Fixed by removing the `create_clock` line; run 10 is clean.

## Next steps
1. Get a data micro-USB cable, then program blinky, then the worm (`impl_2026-11-09_run10_board.bit`): LED 13 should blink 5 times a second; hold the up button ~1 s and LED 15 should light with the speed LEDs counting.
2. Optional: follow one head press in Surfer (`verilog/sim_build/top/top.fst`).
3. Later: 100 MHz timing, the robot (motors instead of LEDs), then learning (R-STDP).
