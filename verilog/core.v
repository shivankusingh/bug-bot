module core #(
    parameter N = 4,                        // neurons
    parameter N_LINKS = 3,                  // chemical links (all senders glued together)
    parameter N_POKES = 2,                  // pokes (head, tail)
    parameter N_POKE_LINKS = 2,             // poke links (all pokes glued together)
    parameter MEM_DIR = "../data/mem/chain" // folder with the .mem files
)(
    input clk,
    input reset,
    input start_step,
    output reg busy,
    input [N_POKES-1:0] pokes
);

    // wiring (loaded once from MEM_DIR, never changes)
    reg [8:0]         link_receiver [0:N_LINKS-1];
    reg signed [10:0] link_weight   [0:N_LINKS-1];
    reg [11:0]        start         [0:N];
    reg [8:0]         poke_receiver [0:N_POKE_LINKS-1];
    reg signed [10:0] poke_weight   [0:N_POKE_LINKS-1];
    reg [11:0]        poke_start    [0:N_POKES];

    // brain state (one slot per neuron, changes every step)
    reg signed [15:0] voltages [0:N-1];
    reg signed [15:0] totals   [0:N-1];
    reg               spikes   [0:N-1];

    reg [7:0] slot;
    reg [15:0] slot_spikes;
    integer i;

    // states
    localparam IDLE = 0,
               CLEAR = 1,
               POKES = 2,
               SPIKES = 3,
               UPDATE = 4;
               
    reg [2:0] state;
    
    reg [7:0] poke_index;

    initial begin
        $readmemh({MEM_DIR, "/link_receiver.mem"}, link_receiver);
        $readmemh({MEM_DIR, "/link_weight.mem"},   link_weight);
        $readmemh({MEM_DIR, "/start.mem"},         start);
        $readmemh({MEM_DIR, "/poke_receiver.mem"}, poke_receiver);
        $readmemh({MEM_DIR, "/poke_weight.mem"},   poke_weight);
        $readmemh({MEM_DIR, "/poke_start.mem"},    poke_start);
        for (i = 0; i < N; i = i + 1) begin
            voltages[i] = 0;
            totals[i]   = 0;
            spikes[i]   = 0;
        end
    end

    reg [8:0] neuron_index; 
    wire signed [15:0] new_voltage;
    wire new_spike;

    lif_math neuron_math(
        .old_voltage(voltages[neuron_index]),
        .total(totals[neuron_index]),
        .new_voltage(new_voltage),
        .spike(new_spike)
    );
    
    always @(posedge clk) begin
        
        if (reset) begin
            neuron_index <= 0;
            busy <= 0;
            state <= IDLE;
        end
        else if (state == IDLE) begin
            if (start_step) begin
                state <= CLEAR;
                busy<=1;
            end
        end
        else if (state == CLEAR) begin
            if (neuron_index == N) begin
                state <= POKES;
                neuron_index <= 0;
                poke_index <= 0;
                slot <= 0;
                slot_spikes <= 0;
            end
            else begin
                neuron_index <= neuron_index + 1;
                totals[neuron_index] <= 0;
            end
        end
        else if (state == POKES) begin
            if(poke_index == N_POKES) begin
                state <= SPIKES;
                poke_index <= 0;
                slot <= 0;
                neuron_index <= 0;
            end
            else if (slot == poke_start[poke_index+1]) begin
                poke_index <= poke_index + 1;
                
        end
            else begin 
                if (pokes[poke_index]==1) begin
                    totals[poke_receiver[slot]] <= totals[poke_receiver[slot]] + poke_weight[slot];
                end
                slot <= slot + 1;

            end 
            
        


        end

        else if (state == SPIKES) begin

                if (neuron_index == N) begin
                    state <= UPDATE;
                    neuron_index <= 0;
                    slot_spikes <= 0;
                end
                else if (slot_spikes == start[neuron_index+1])begin
                    neuron_index <= neuron_index + 1;
                end
                else begin
                    if (spikes[neuron_index] == 1) begin
                        totals[link_receiver[slot_spikes]] <= totals[link_receiver[slot_spikes]] + link_weight[slot_spikes];
                        slot_spikes <= slot_spikes + 1;
                    end
                    else begin 
                        neuron_index <= neuron_index + 1;
                        slot_spikes <= slot_spikes + (start[neuron_index+1] - slot_spikes);
                    end
                end

        end
        else if (state == UPDATE) begin
            if (neuron_index == N) begin
                state <= IDLE;
                busy <= 0;
                neuron_index <= 0;
            end
            else begin
                voltages[neuron_index] <= new_voltage;
                spikes[neuron_index] <= new_spike;
                neuron_index <= neuron_index + 1;
            end
        end
        
    end
    
endmodule