module core #(
    parameter N = 4,                        // neurons
    parameter N_LINKS = 3,                  // chemical links (all senders glued together)
    parameter N_POKES = 2,                  // pokes (head, tail)
    parameter N_POKE_LINKS = 2,             // poke links (all pokes glued together)
    parameter N_PIPES = 1,                  // pipes (all pipes glued together)
    parameter MEM_DIR = "../data/mem/chain", // folder with the .mem files
    parameter MUSCLE_LEAK_FACTOR = 2,
    parameter STOP_BELOW = 8
)(
    input clk,
    input reset,
    input start_step,
    output reg busy,
    input [N_POKES-1:0] pokes,
    output reg [6:0] wheel_speed,
    output reg [1:0] wheel_direction,
    output reg [6:0] back_muscle,
    output reg [6:0] forward_muscle
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
    reg [1:0] motor_role    [0:N-1];
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
               PIPES_SAVE = 4,
               PIPES_A = 5,
               PIPES_B = 6,
               UPDATE_READ = 7,
               UPDATE_SAVE = 8,
               MUSCLE_LEAK = 9,
               MUSCLE_UPDATE = 10;
               
    reg [3:0] state;
    
    reg [7:0] poke_index;
    reg [2:0] PIPE_K;

    reg [3:0] pipe_shift;
    
    wire signed [19:0] pipe_flow;
    reg signed [15:0] pipe_flow_addition;
    reg [7:0] pipe_size_to_reg;
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
        $readmemh({MEM_DIR, "/motor_role.mem"},       motor_role);
        for (i = 0; i < N; i = i + 1) begin
            voltages[i] = 0;
            totals[i]   = 0;
            spikes[i]   = 0;
        end
    end

    reg [10:0] neuron_index; 
    wire signed [15:0] new_voltage;
    reg signed [15:0] old_voltage_reg;
    reg signed [15:0] totals_reg;

    reg [8:0] pipe_a_neuron_index_reg;
    reg [8:0] pipe_b_neuron_index_reg;

    wire new_spike;
    lif_math neuron_math(
        .old_voltage(old_voltage_reg),
        .total(totals_reg),
        .new_voltage(new_voltage),
        .spike(new_spike)
    );
        
        assign totals_temp_val_holder_b = (spikes[pipe_a_neuron_index_reg] ==1) ?  ( pipe_size_to_reg * PIPE_K) :  0;
       
        assign totals_temp_val_holder_a = (spikes[pipe_b_neuron_index_reg] ==1) ?  ( pipe_size_to_reg * PIPE_K) : 0;
        assign pipe_flow  =((pipe_flow_addition* $signed({1'b0,pipe_size_to_reg})) >>> pipe_shift);

    always @(posedge clk) begin
        
        if (reset) begin
            neuron_index <= 0;
            busy <= 0;
            state <= IDLE;
            back_muscle <= 0;
            forward_muscle <= 0;
            wheel_speed <= 0;
            wheel_direction <= 0;
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
                    state <= PIPES_SAVE;
                    neuron_index <= 0;
                    slot_spikes <= 0;
                    PIPE_K <= 1;
                    pipe_shift <= 10;
                    totals_reg <= 0;
                old_voltage_reg <= 0;
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


        // PIPES takes three ticks per pipe, so totals gets one write per tick.
        // Tick 1: save everything this pipe needs into regs.
        else if (state == PIPES_SAVE) begin
            if (neuron_index == N_PIPES) begin
                state <= MUSCLE_LEAK;
                neuron_index <= 0;
                totals_reg <= 0;
                old_voltage_reg <= 0;
            end
            else begin
                state <= PIPES_A;
                pipe_flow_addition <= voltages[pipe_a[neuron_index]] - voltages[pipe_b[neuron_index]];
                pipe_size_to_reg <= pipe_size[neuron_index];
                pipe_a_neuron_index_reg <= pipe_a[neuron_index];
                pipe_b_neuron_index_reg <= pipe_b[neuron_index];
            end
        end

        // Tick 2: write side a.
        else if (state == PIPES_A) begin
            state <= PIPES_B;
            totals[pipe_a_neuron_index_reg] <= totals[pipe_a_neuron_index_reg] - pipe_flow + totals_temp_val_holder_a;
        end

        // Tick 3: write side b, then move to the next pipe.
        else if (state == PIPES_B) begin
            state <= PIPES_SAVE;
            totals[pipe_b_neuron_index_reg] <= totals[pipe_b_neuron_index_reg] + pipe_flow + totals_temp_val_holder_b;
            neuron_index <= neuron_index + 1;
        end
        else if (state == MUSCLE_LEAK) begin
            back_muscle <= back_muscle - (back_muscle >> MUSCLE_LEAK_FACTOR);
            forward_muscle <= forward_muscle - (forward_muscle >> MUSCLE_LEAK_FACTOR);
            state <= UPDATE_READ;
        
        end

        // UPDATE takes two ticks per neuron.
        // Tick 1: read the neuron into the regs that feed lif_math.
        else if (state == UPDATE_READ) begin
            if (neuron_index == N) begin
                state <= MUSCLE_UPDATE;
                neuron_index <= 0;
              
            end
            else begin
                state <= UPDATE_SAVE;
                old_voltage_reg <= voltages[neuron_index];
                totals_reg <= totals[neuron_index];
            end
        end

        // Tick 2: lif_math's answer is ready, so save it and move to the next neuron.
        else if (state == UPDATE_SAVE) begin
            state <= UPDATE_READ;
            voltages[neuron_index] <= new_voltage;
            spikes[neuron_index] <= new_spike;
            // muscles
            if (motor_role[neuron_index] == 1 && new_spike == 1) begin
                back_muscle <= back_muscle + 1;
            end
            else if (motor_role[neuron_index] == 2 && new_spike==1) begin
                forward_muscle <= forward_muscle + 1;
            end
            neuron_index <= neuron_index + 1;
        
        
    end
   
    else if (state == MUSCLE_UPDATE) begin
        if(back_muscle < STOP_BELOW && forward_muscle < STOP_BELOW)begin
            wheel_speed <= 0;
            wheel_direction <= 0;
            state <= IDLE;
            busy <= 0;
        end
        else if(back_muscle > forward_muscle)begin
            wheel_speed <= back_muscle - forward_muscle;
            wheel_direction <= 1;
            state <= IDLE;
            busy <= 0;
        end
        else begin
            wheel_speed <= forward_muscle - back_muscle;
            wheel_direction <= 2;
            state <=IDLE;
            busy<=0;
        end
    end
    end
endmodule