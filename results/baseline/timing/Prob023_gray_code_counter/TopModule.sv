module TopModule(
   input   clk,
   input   rst_n,

   output  reg [3:0] gray_out
);
reg       step_toggle;
reg [3:0] bin_out;
reg [3:0] bin_add_wire;
wire [3:0] gray_wire;

always @(*) begin
   bin_out[3] = gray_out[3];
   bin_out[2] = gray_out[2] ^ bin_out[3];
   bin_out[1] = gray_out[1] ^ bin_out[2];
   bin_out[0] = gray_out[0] ^ bin_out[1];
end

always @(*) begin
   bin_add_wire = bin_out + 4'b0001;
end

assign gray_wire = (bin_add_wire >> 1) ^ bin_add_wire;

always @(posedge clk or negedge rst_n) begin
   if (rst_n == 1'b0) begin
      gray_out     <= 4'b0000;
      step_toggle  <= 1'b0;
   end
   else begin
      step_toggle <= ~step_toggle;
      if (step_toggle == 1'b1)
         gray_out <= gray_wire;
   end
end
endmodule
