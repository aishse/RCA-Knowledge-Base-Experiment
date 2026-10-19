module TopModule(
    input                  clk      ,  
    input                  rst_n    ,
    input                  valid_in ,
    input       [7:0]      data_in  ,
  
    output  reg            valid_out,
    output  reg [15:0]     data_out
);
    reg [7:0] data_r;
    reg       flag;
    reg       pending_valid;

    always @(posedge clk or negedge rst_n) begin
        if (~rst_n) begin
            data_r    <= 8'd0;
            flag      <= 1'b0;
            pending_valid <= 1'b0;
            data_out  <= 16'd0;
            valid_out <= 1'b0;
        end else begin
            valid_out <= pending_valid;
            pending_valid <= 1'b0;

            if (valid_in) begin
                if (!flag) begin
                    data_r <= data_in;
                    flag   <= 1'b1;
                end else begin
                    data_out      <= {data_r, data_in};
                    pending_valid <= 1'b1;
                    flag          <= 1'b0;
                end
            end
        end
    end
endmodule
