module top_module(
input clk,
  input reset,
  input [1:0] pokes,
output spikes_a,
  output spikes_b,
output spikes_c,
output spikes_inhib,
  output wire signed [15:0] v_a,
    output wire signed [15:0] v_b,
    output wire signed [15:0] v_c,
    output wire signed [15:0] v_inhib

);


    lif_neuron #(
      .WEIGHT_ONE(16'sd300),
      .WEIGHT_TWO(16'sd0),
      .WEIGHT_THREE(16'sd0)
    )neuron_a (
      .clk(clk),
      .reset(reset),
      .spikes_in({pokes[1],1'b0,1'b0}),
      .voltage(v_a),
      .spike(spikes_a)
    );
    
    
     lif_neuron #(
      .WEIGHT_ONE(16'sd300),
       .WEIGHT_TWO(-16'sd400),
      .WEIGHT_THREE(16'sd0)
     )neuron_b (
      .clk(clk),
      .reset(reset),
       .spikes_in({spikes_a,spikes_inhib,1'b0}),
       .voltage(v_b),
       .spike(spikes_b)
    );
    
     lif_neuron #(
      .WEIGHT_ONE(16'sd300),
       .WEIGHT_TWO(16'sd0),
      .WEIGHT_THREE(16'sd0)
     )neuron_c (
      .clk(clk),
      .reset(reset),
       .spikes_in({spikes_b,1'b0,1'b0}),
       .voltage(v_c),
       .spike(spikes_c)
    );
    
lif_neuron #(
      .WEIGHT_ONE(16'sd300),
       .WEIGHT_TWO(16'sd0),
      .WEIGHT_THREE(16'sd0)
)neuron_I (
      .clk(clk),
      .reset(reset),
  .spikes_in({pokes[0],1'b0,1'b0}),
  .voltage(v_inhib),
  .spike(spikes_inhib)
    );
    
  endmodule
