module core #(
    parameter N = 4,                        // neurons
    parameter N_LINKS = 3,                  // chemical links (all senders glued together)
    parameter N_POKES = 2,                  // pokes (head, tail)
    parameter N_POKE_LINKS = 2,             // poke links (all pokes glued together)
    parameter N_PIPES = 1,                  // pipes (all pipes glued together)
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
    reg [8:0]         pipe_a        [0:N_PIPES-1];
    reg [8:0]         pipe_b        [0:N_PIPES-1];
    reg [7:0] pipe_size     [0:N_PIPES-1];
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
               PIPES = 4,
               UPDATE = 5;
               
    reg [2:0] state;
    
    reg [7:0] poke_index;
    reg [2:0] PIPE_K;

    reg [3:0] pipe_shift;
    wire signed [19:0] pipe_flow;
    reg flipflopper;
    wire signed [15:0] totals_temp_val_holder_a;
    wire signed [15:0] totals_temp_val_holder_b;
    initial begin
        $readmemh({MEM_DIR, "/link_receiver.mem"}, link_receiver);
        $readmemh({MEM_DIR, "/link_weight.mem"},   link_weight);
        $readmemh({MEM_DIR, "/start.mem"},         start);
        $readmemh({MEM_DIR, "/poke_receiver.mem"}, poke_receiver);
        $readmemh({MEM_DIR, "/poke_weight.mem"},   poke_weight);
        $readmemh({MEM_DIR, "/poke_start.mem"},    poke_start);
        $readmemh({MEM_DIR, "/pipe_a.mem"},          pipe_a);
        $readmemh({MEM_DIR, "/pipe_b.mem"},          pipe_b);
        $readmemh({MEM_DIR, "/pipe_size.mem"},       pipe_size);
        for (i = 0; i < N; i = i + 1) begin
            voltages[i] = 0;
            totals[i]   = 0;
            spikes[i]   = 0;
        end
    end

    reg [10:0] neuron_index; 
    wire signed [15:0] new_voltage;
    wire new_spike;

    lif_math neuron_math(
        .old_voltage(voltages[neuron_index]),
        .total(totals[neuron_index]),
        .new_voltage(new_voltage),
        .spike(new_spike)
    );
        
        assign totals_temp_val_holder_b = (spikes[pipe_a[neuron_index]] ==1) ?  ( pipe_size[neuron_index] * PIPE_K) :  0;
       
        assign totals_temp_val_holder_a = (spikes[pipe_b[neuron_index]] ==1) ?  ( pipe_size[neuron_index] * PIPE_K) : 0;
        assign pipe_flow  =(((voltages[pipe_a[neuron_index]] - voltages[pipe_b[neuron_index]]) * $signed({1'b0,pipe_size[neuron_index]})) >>> pipe_shift);

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
                    state <= PIPES;
                    neuron_index <= 0;
                    slot_spikes <= 0;
                    PIPE_K <= 1;
                    pipe_shift <= 10;
                    flipflopper <= 0;
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


        else if (state == PIPES) begin
            if (neuron_index == N_PIPES) begin
                state <= UPDATE;
                neuron_index <= 0;
                flipflopper <= 0;
            end
            
            else begin

            if (flipflopper == 0) begin
            totals[pipe_a[neuron_index]] <= totals[pipe_a[neuron_index]] - pipe_flow + totals_temp_val_holder_a;
            flipflopper <= 1;
            end
            else begin
            totals[pipe_b[neuron_index]] <= totals[pipe_b[neuron_index]] + pipe_flow + totals_temp_val_holder_b;
            flipflopper <= 0;
                        neuron_index <= neuron_index + 1;

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