# bug-bot

Running the C. elegans connectome (302 neurons) as a spiking neural network on an FPGA to drive a small robot. Long-term: add reinforcement learning, then scale to the fruit fly connectome (~140k neurons) for a drone.

## How to work with me (most important)
- **I write the core logic myself:** the Python neuron model, the network update loops, and all Verilog RTL (neuron datapath, synapse memory, spike routing, scheduler). For these, explain the concept and tell me what to try. Do **not** write the code unless I'm stuck or explicitly ask.
- **You can write tooling:** connectome parsers, testbenches/cocotb harnesses, file converters (e.g. `.mem` files), build/sim scripts, plotting.
- Explain anything you write. I won't commit code I can't explain line by line.
- I'm a hardware beginner with mostly software experience. Explain simply, one step at a time, with concrete examples (trace actual numbers). I learn best visually: diagrams, tables, organized layouts.
- When I'm confused, re-explain differently instead of adding new terms. Define any new term in plain words.
- Ask before reorganizing files, deleting anything, or changing the model math.

## Git rules
- This repo is **public**. Never commit secrets, API keys, passwords, personal information, or any code/data from outside sources I haven't confirmed I'm allowed to share.
- Do **not** add AI attribution to commits: no `Co-Authored-By` lines, no "Generated with" footers, no session links.
- Before committing: show `git status`, explain what's being committed, and wait for my OK before `git push`.
- Write short, descriptive commit messages (e.g. "Refactor Python model to sparse connection lists").

## Repo layout
<!-- Claude Code: keep these paths matched to the actual repo. -->
- `CLAUDE.md`: this file
- `python/`: reference model (e.g. `chain_model.py`), connectome parser, scripts
  - `python/bug_bot.ipynb`: current Python reference model (notebook)
- `verilog/`: RTL design files and testbenches
- `data/`: golden vectors and connectome data files
- `logs/`: day-by-day project log
- Python runs via `.venv/bin/python` (local virtual environment with numpy and matplotlib; ignored by git).

## Current state
- 4-neuron test network: A → B → C chain, plus inhibitory neuron I onto B.
- Verilog: `lif_neuron` module (3 weighted inputs, parameters for weights) instantiated 4 times in `top_module`, hand-wired. Passes a self-checking testbench against Python golden vectors.
- Python reference model uses **sparse connection lists** and is verified to reproduce the original golden files exactly.

## Model conventions (Python and Verilog must match exactly)
- Integer-only LIF: `v = v - (v >> 3) + total`; spike if `v >= 256`, then reset `v = 0`.
- `total` (this step's input, reset to 0 each step) is kept separate from `v` (neuron memory). The leak uses the old `v` before input is added.
- Neuron-to-neuron spikes arrive with a **one-step delay** (from `last_spikes`). Pokes (external inputs) act on the **same step**.
- Sparse format: `connections[sender] = [(receiver, weight), ...]`; `poke_connections[poke] = [(receiver, weight), ...]`.
- 4-neuron test network: indices A=0, B=1, C=2, I=3. Weights: A→B 300, B→C 300, I→B −400; poke 0 → A 300, poke 1 → I 300.
- Golden outputs (6 files): `chain_inputs.txt` (`row[0]*2 + row[1]`), `chain_expected_spikes.txt` (`A*8 + B*4 + C*2 + I`), and `chain_expected_va/vb/vc/vi.txt` (16-bit masked, `%04x`).
- Verilog wiring: `spikes_in` is 3 bits, with `[2]` = WEIGHT_ONE input.

## Verification rule
Any change to the Python model must reproduce the existing golden files exactly unless the math is changed on purpose. If the math changes, change Python first, then Verilog, then regenerate golden files.

## Known issues
- Python ints don't overflow; wrap/saturation should be modeled inside `neuron_model`, not only masked at export.
- Verilog: 16-bit `total`/`voltage` with no saturation; no voltage floor.
- One module instance per neuron won't scale to 302.
- Most real C. elegans neurons use graded potentials, not spikes. LIF is a deliberate simplification.

## Roadmap
1. ✅ Python model refactored to sparse connection lists.
2. **Next:** load the real connectome (Cook et al. 2019 or OpenWorm data). Claude writes the parser that outputs the `connections` format. I decide: synapse count → integer weight scaling, which synapses are inhibitory, how to handle gap junctions, which neurons get sensor inputs.
3. Sanity check: poking touch-sensory neurons should drive the backward/forward command interneurons.
4. Local sim flow: Icarus/Verilator + cocotb (Python testbenches comparing against the model) + Surfer/GTKWave.
5. Hardware: time-multiplexed core: one neuron-update unit looping over all neurons, voltages in BRAM, synapses in CSR format, two-phase timestep (deliver spikes, then update neurons), double-buffered spike flags. First test: load the 4-neuron network from memory files and match its output.
6. FPGA board + robot I/O (sensors → sensory neurons, motor neurons → motors), then RL.
7. Later: scale to the fruit fly connectome.

## Project log
Day-by-day log files in `logs/`, each with: what I did, what I learned, mistakes fixed, and next steps. Update "Current state" and "Roadmap" here when a milestone is hit.