module TopModule(
	input clk,
	input rst_n,
	input set,
	input [3:0] set_num,
	output reg [3:0]number,
	output reg zero
	);
	reg [3:0]num;
	
	always @(posedge clk or negedge rst_n)
		if (!rst_n)
			begin 
				num <= 4'b0;
				number <= 4'b0;
				zero <= 1'b1;
			end
		else if(set)
			begin
				num <= set_num;
				number <= set_num;
				zero <= (set_num == 4'd0);
			end
		else 
			begin
				num <= num + 4'd1;
				number <= num + 4'd1;
				zero <= ((num + 4'd1) == 4'd0);
			end

endmodule
