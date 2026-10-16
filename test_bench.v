// Code your testbench here
module tb();

  reg clk;
  reg reset;
  reg [1:0] pokes;
  wire spikes_a;
  wire spikes_b;
  wire spikes_c;
  wire spikes_inhib;
  wire signed [15:0] v_a;
  wire signed [15:0] v_b;
  wire signed [15:0] v_c;
  wire signed [15:0] v_inhib;
  integer i;
  reg [1:0] chained_pokes_input [0:9];
  reg signed [15:0] chained_expected_v_a [0:9];
  reg signed [15:0] chained_expected_v_b [0:9];
  reg signed [15:0] chained_expected_v_c [0:9];
  reg signed [15:0] chained_expected_v_inhib [0:9];
  reg [3:0] chained_expected_spikes [0:9];
  

  top_module test_bench_top_module(
    .clk(clk),
    .reset(reset),
    .pokes(pokes),
    .spikes_a(spikes_a),
    .spikes_b(spikes_b),
    .spikes_c(spikes_c),
    .spikes_inhib(spikes_inhib),
    .v_a(v_a),
    .v_b(v_b),
    .v_c(v_c),
    .v_inhib(v_inhib)
  );

  // clock: starts at 0, flips every 5 → one rising edge every 10
  initial begin
    clk = 0;
  end

  always begin
    #5;
    clk = !clk;
  end

  // the test
  initial begin
    $readmemh("chain_expected_spikes.txt", chained_expected_spikes);
    $readmemh("chain_expected_va.txt", chained_expected_v_a);
    $readmemh("chain_expected_vb.txt", chained_expected_v_b);
    $readmemh("chain_expected_vc.txt", chained_expected_v_c);
    $readmemh("chain_expected_vi.txt", chained_expected_v_inhib);
    $readmemh("chain_inputs.txt", chained_pokes_input);

    // reset
    reset = 1;
    pokes = 0;
    @(posedge clk); #1; reset = 0;

    // feed one input per tick and print the result
    for (i = 0; i < 10; i = i + 1) begin
      pokes = chained_pokes_input[i];        // put this step's input on the wire
      @(posedge clk);             // neuron takes one step
      #1;                         // let the outputs update
      $display("step %3d  poke_a %2d  poke_i %2d spikes_a %2d  spikes_b %2d  spikes_c %2d spikes_inhib %2d v_b %5d", i, pokes[1], pokes[0],spikes_a, spikes_b, spikes_c, spikes_inhib, v_b);
 if ({spikes_a, spikes_b, spikes_c, spikes_inhib} !== chained_expected_spikes[i] ||
    v_a     !== chained_expected_v_a[i] ||
    v_b     !== chained_expected_v_b[i] ||
    v_c     !== chained_expected_v_c[i] ||
     v_inhib !== chained_expected_v_inhib[i]) begin 
   $display("MISMATCH at step %0d", i);
$display("  spikes ABCI: expected %b, got %b",
           chained_expected_spikes[i], {spikes_a, spikes_b, spikes_c, spikes_inhib});
  $display("  v_a: expected %0d, got %0d", chained_expected_v_a[i], v_a);
  $display("  v_b: expected %0d, got %0d", chained_expected_v_b[i], v_b);
  $display("  v_c: expected %0d, got %0d", chained_expected_v_c[i], v_c);
  $display("  v_i: expected %0d, got %0d", chained_expected_v_inhib[i], v_inhib);
  $finish;
end
    end
    $display("PASS: all 10 steps match");
    $finish;
  end

endmodule
