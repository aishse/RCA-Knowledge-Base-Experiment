module TopModule(
    input       [3:0]       A_in  ,
    input       [3:0]       B_in  ,
    input                   C_1   ,
  
    output   wire           CO    ,
    output   wire [3:0]     S
);
    wire [3:0] G, P, C;
    wire p0_c1;
    wire p1_g0, p1_p0_c1;
    wire p2_g1, p2_p1_g0, p2_p1_p0_c1;
    wire p3_g2, p3_p2_g1, p3_p2_p1_g0, p3_p2_p1_p0_c1;

    and (G[0], A_in[0], B_in[0]);
    and (G[1], A_in[1], B_in[1]);
    and (G[2], A_in[2], B_in[2]);
    and (G[3], A_in[3], B_in[3]);

    xor (P[0], A_in[0], B_in[0]);
    xor (P[1], A_in[1], B_in[1]);
    xor (P[2], A_in[2], B_in[2]);
    xor (P[3], A_in[3], B_in[3]);

    and (p0_c1, P[0], C_1);
    or  (C[0], G[0], p0_c1);

    and (p1_g0, P[1], G[0]);
    and (p1_p0_c1, P[1], P[0], C_1);
    or  (C[1], G[1], p1_g0, p1_p0_c1);

    and (p2_g1, P[2], G[1]);
    and (p2_p1_g0, P[2], P[1], G[0]);
    and (p2_p1_p0_c1, P[2], P[1], P[0], C_1);
    or  (C[2], G[2], p2_g1, p2_p1_g0, p2_p1_p0_c1);

    and (p3_g2, P[3], G[2]);
    and (p3_p2_g1, P[3], P[2], G[1]);
    and (p3_p2_p1_g0, P[3], P[2], P[1], G[0]);
    and (p3_p2_p1_p0_c1, P[3], P[2], P[1], P[0], C_1);
    or  (C[3], G[3], p3_g2, p3_p2_g1, p3_p2_p1_g0, p3_p2_p1_p0_c1);

    xor (S[0], P[0], C_1);
    xor (S[1], P[1], C[0]);
    xor (S[2], P[2], C[1]);
    xor (S[3], P[3], C[2]);

    buf (CO, C[3]);
     
endmodule
