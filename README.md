# bug-bot

Putting a real animal's brain on a chip: the *C. elegans* worm's 302-neuron connectome,
implemented as a spiking neural network on an FPGA and driving a small robot.

**Status:** the Python reference model is complete: the real worm brain (300 neurons) reacts
correctly to touch, all the way to the wheels. Next: the scalable Verilog core.

**Live demo:** [shivankusingh.github.io/bug-bot](https://shivankusingh.github.io/bug-bot/): a 3D view of the
worm's 300 neurons. Poke the head or tail and watch the brain decide which way the robot moves.

## How it works
- **Neurons:** each one is an integer **leaky integrate-and-fire (LIF)** model. Every tick the voltage
  leaks (`v - (v >> 3)`), adds its input, fires at a threshold of 256 and resets to 0. It never drops
  below −512, so every voltage fits easily in 16 bits.
- **Wiring:** 3,669 chemical synapses (weight = synapse count × 10, one-tick delay) and 1,087 gap
  junctions from the real connectome. Gap junctions pass voltage both ways, plus a small push when a
  neuron fires.
- **Excite or inhibit:** signs come from receptor data. Where the data can't decide, a circuit rule
  uses known biology: touch sensors block the opposite direction, and command and motor neurons on
  the same team (backward or forward) help each other while opposite teams block each other.
- **Robot readout:** backward (DA/VA) and forward (DB/VB) motor spikes fill two leaky "muscle"
  buckets; the fuller one sets the wheel direction and speed.
- **Verification:** every design is built first as a **Python reference model**, then in **Verilog**,
  and checked bit-for-bit against golden files with a self-checking testbench.

## Progress
- [x] Single LIF neuron in Python and Verilog, outputs match exactly
- [x] 3-input neuron with an inhibitory input (signed arithmetic in Verilog), verified bit-exact
- [x] 4-neuron network in Python: excitatory chain A → B → C plus an inhibitory interneuron
- [x] 4-neuron network in Verilog, verified bit-exact
- [x] Load the real C. elegans wiring (300 neurons, chemical synapses and gap junctions)
- [x] Touch test in Python: head touch → backward, tail touch → forward, brain goes quiet afterwards
- [x] Motor neurons and robot wheel readout in Python, both directions
- [x] 16-bit safe model (voltage floor) and golden files for the full network
- [x] Live 3D demo website
- [ ] Scalable Verilog core (one neuron circuit looping over all neurons, wiring in memory)
- [ ] Full brain on real FPGA hardware
- [ ] More senses (nose touch, then food and steering)
- [ ] The robot: real sensors and motors

## Files
- `python/bug_bot.ipynb`: 4-neuron reference model (test bench for the Verilog)
- `python/touch_test.ipynb`: the full worm brain: touch test, robot readout, exports
- `python/connectome_parser.py`: builds the network from the raw data (weights, sign rules)
- `python/connectome_all.py`, `python/touch_circuit.py`: the generated networks (300 and 14 neurons)
- `python/plot_run.py`, `python/golden.py`, `python/export_web.py`: plotting, golden files, website data
- `verilog/`: LIF neuron, 4-neuron network and its self-checking testbench
- `data/`: golden files (`chain_*` for 4 neurons, `full_*` for the whole brain)
- `docs/`: the demo website
- `logs/log.md`: day-by-day development log

## Data sources and credits
- **Wiring (who connects to whom, and how strongly):** Cook SJ, Jarrell TA, Brittin CA, et al.
  "Whole-animal connectomes of both *Caenorhabditis elegans* sexes." *Nature* 571, 63–71 (2019).
  [doi:10.1038/s41586-019-1352-7](https://doi.org/10.1038/s41586-019-1352-7).
  Hermaphrodite adjacency matrices, SI 5 (corrected July 2020).
- **Excitatory / inhibitory signs:** Fenyves BG, Szilágyi GS, Vassy Z, Sőti C, Csermely P.
  "Synaptic polarity and sign-balance prediction using gene expression data in the
  *Caenorhabditis elegans* chemical synapse neuronal connectome network."
  *PLOS Computational Biology* 16(12): e1007974 (2020).
  [doi:10.1371/journal.pcbi.1007974](https://doi.org/10.1371/journal.pcbi.1007974).
  S1 Data, used under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
- **Touch-circuit sign rule** (touch neurons inhibit the command interneurons for the opposite
  direction): Chalfie M, Sulston JE, White JG, Southgate E, Thomson JN, Brenner S.
  "The neural circuit for touch sensitivity in *Caenorhabditis elegans*."
  *Journal of Neuroscience* 5(4), 956–964 (1985).
- **Data download:** the Cook et al. spreadsheet was obtained from OpenWorm's
  [ConnectomeToolbox](https://github.com/openworm/ConnectomeToolbox) (MIT license).
