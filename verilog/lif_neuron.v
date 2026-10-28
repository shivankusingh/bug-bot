// Code your design here
module lif_neuron #(
  parameter signed[15:0] WEIGHT_ONE = 16'sd300,
  parameter signed[15:0] WEIGHT_TWO = 16'sd50,
  parameter signed [15:0] WEIGHT_THREE = -16'sd150
)(
  input clk,
  input reset,
  input [2:0] spikes_in,
  output reg signed [15:0] voltage,
  output reg spike
 
);
  wire pos_1;
  wire pos_2;
  wire pos_3;

  assign pos_1= spikes_in[2];
  assign pos_2 = spikes_in[1];
  assign pos_3 = spikes_in[0];
  
  
  wire signed [15:0] total;
  wire signed [15:0] tempVoltage;


  assign total = (pos_1 ? WEIGHT_ONE : 16'sd0)
    + (pos_2 ? WEIGHT_TWO : 16'sd0)
    + (pos_3 ? WEIGHT_THREE : 16'sd0);
  			
    
                 
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


