# bug-bot

Putting a real animal's brain on a chip: the *C. elegans* worm's 302-neuron connectome,
implemented as a spiking neural network on an FPGA and driving a small robot.

**Status:** in progress (foundations phase)

**Live demo:** [shivankusingh.github.io/bug-bot](https://shivankusingh.github.io/bug-bot/): a 3D view of the
worm's 300 neurons. Poke the head or tail and watch the brain decide which way the robot moves.

## How it works
- Each neuron is an integer **leaky integrate-and-fire (LIF)** model: voltage leaks each tick
  (`v - (v >> 3)`), adds weighted input spikes, fires at a threshold of 256, then resets.
- Neurons are connected by excitatory (positive) and inhibitory (negative) weighted synapses,
  with a one-tick synaptic delay.
- Every design is built first as a **Python reference model**, then in **Verilog**, and checked
  bit-for-bit with a self-checking testbench.

## Progress
- [x] Single LIF neuron in Python and Verilog, outputs match exactly
- [x] 3-input neuron with an inhibitory input (signed arithmetic in Verilog), verified bit-exact
- [x] 4-neuron network in Python: excitatory chain A → B → C plus an inhibitory interneuron
- [X] 4-neuron network in Verilog
- [ ] Run on real FPGA hardware (Vivado)
- [x] Load real C. elegans wiring (touch-withdrawal circuit first)
- [ ] Full 302-neuron brain in hardware
- [ ] Sensors + motors: robot reacts to touch

## Files
- `bug_bot.ipynb`: Python reference models
- `lif_neuron.v`: Verilog LIF neuron
- `tb_lif_neuron.v`: self-checking testbench
- `log.md`: day-by-day development log

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
