module TopModule(
	input 				clk 		,   
	input 				rst_n		,
	input		[7:0]	data_in		,
	input				valid_a		,
	input	 			ready_b		,
 
 	output		 		ready_a		,
 	output	reg			valid_b		,
	output  reg [9:0] 	data_out
);
reg 	[1:0]		data_cnt;
reg     [9:0]       sum_acc;

assign ready_a = !valid_b | ready_b;

always @(posedge clk or negedge rst_n ) begin
	if(!rst_n) begin
		data_cnt <= 'd0;
		sum_acc  <= 'd0;
		valid_b  <= 'd0;
		data_out <= 'd0;
	end else begin
		if(valid_b && ready_b)
			valid_b <= 1'd0;

		if(valid_a && ready_a) begin
			if(data_cnt == 2'd3) begin
				data_cnt <= 'd0;
				data_out <= sum_acc + data_in;
				valid_b  <= 1'd1;
			end else begin
				data_cnt <= data_cnt + 1'd1;
				sum_acc  <= (data_cnt == 2'd0) ? data_in : (sum_acc + data_in);
			end
		end
	end
end


endmodule
