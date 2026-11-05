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
