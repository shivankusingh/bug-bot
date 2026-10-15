// Code your design here
module lif_neuron(
  input clk,
  input reset,
  input [2:0] spikes_in,
  output reg signed [15:0] voltage,
  output reg spike
);
  wire a;
  wire b;
  wire c;
  assign a = spikes_in[2];
  assign b = spikes_in[1];
  assign c = spikes_in[0];
  wire signed [15:0] total;
  wire signed [15:0] tempVoltage;
  localparam signed[15:0] WEIGHT_ONE = 16'sd300;
  localparam signed[15:0] WEIGHT_TWO = 16'sd50;
  localparam signed [15:0] WEIGHT_THREE = -16'sd150;
  assign total = (a ? WEIGHT_ONE : 16'sd0)
             + (b ? WEIGHT_TWO : 16'sd0)
             + (c ? WEIGHT_THREE : 16'sd0);
    
                 
  assign tempVoltage = voltage -(voltage>>>3)+ total;
          
                  
         
  always @(posedge clk) begin
    spike <= 1'b0;
    if(reset) begin

      voltage <=0;
    end
    else begin
      voltage <= tempVoltage;
     
      if((tempVoltage)>=(16'sd256)) begin
      spike <= 1'b1;
      
      voltage <= 16'sd0;
    end
    end
  end
endmodule
