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
