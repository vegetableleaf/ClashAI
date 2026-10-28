| det | mb | total ms (ms_median.total) | gen_batch ms | forward_ex_gen ms | backward ms | clip ms | optim ms | rows_per_s | ms_per_row | peak_mb | kernels_per_step | gpu_kernel_ms_per_step | prof_flops_per_step (GFLOP) | achieved_tflops |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 64 | 102 | 13.1 | 36.3 | 46.6 | 2.45 | 2.85 | 625 | 1.60 | 1.30E+003 | 5.19E+003 | 142 | 102 | 1.00 |
| 1 | 256 | 170 | 42.3 | 59.8 | 62.5 | 3.02 | 3.48 | 1.51E+003 | 0.664 | 2.79E+003 | 5.26E+003 | 267 | 384 | 2.26 |
| 1 | 1024 | 441 | 166 | 102 | 166 | 3.46 | 3.48 | 2.32E+003 | 0.430 | 8.79E+003 | 5.71E+003 | 1.19E+003 | 1.43E+003 | 3.25 |
| 0 | 64 | 95.4 | 13.0 | 35.9 | 41.1 | 2.23 | 2.77 | 671 | 1.49 | 1.30E+003 | 5.19E+003 | 139 | 102 | 1.07 |
| 0 | 256 | 170 | 41.6 | 60.5 | 62.4 | 3.00 | 3.42 | 1.50E+003 | 0.666 | 2.79E+003 | 5.26E+003 | 264 | 384 | 2.26 |
| 0 | 1024 | 438 | 164 | 102 | 165 | 3.33 | 3.54 | 2.34E+003 | 0.428 | 8.79E+003 | 5.71E+003 | 1.18E+003 | 1.43E+003 | 3.27 |

```text
----------------------------------------------------------------------  ------------  ------------  ------------  ------------  ------------  ------------  ------------  ------------  ------------  ------------  ------------  
                                                                  Name    Self CPU %      Self CPU   CPU total %     CPU total  CPU time avg     Self CUDA   Self CUDA %    CUDA total  CUDA time avg    # of Calls  Total MFLOPs  
----------------------------------------------------------------------  ------------  ------------  ------------  ------------  ------------  ------------  ------------  ------------  ------------  ------------  ------------  
                                                               forward         0.00%       0.000us         0.00%       0.000us       0.000us     305.082ms       129.74%     305.082ms     101.694ms             3            --  
                                                             gen_batch         0.00%       0.000us         0.00%       0.000us       0.000us     236.981ms       100.78%     236.981ms      39.497ms             6            --  
                                                               forward         1.58%      27.535ms        17.51%     305.546ms     101.849ms       0.000us         0.00%      56.024ms      18.675ms             3            --  
                                  aten::_transformer_encoder_layer_fwd         0.10%       1.713ms         4.32%      75.423ms       2.514ms       0.000us         0.00%      37.197ms       1.240ms            30            --  
autograd::engine::evaluate_function: ScaledDotProductEfficientAtten...         0.02%     366.752us         0.30%       5.164ms     286.898us       0.000us         0.00%      33.204ms       1.845ms            18            --  
                           ScaledDotProductEfficientAttentionBackward0         0.01%     185.783us         0.27%       4.797ms     266.523us       0.000us         0.00%      33.204ms       1.845ms            18            --  
                aten::_scaled_dot_product_efficient_attention_backward         0.02%     323.214us         0.26%       4.612ms     256.202us       0.000us         0.00%      33.204ms       1.845ms            18            --  
                                   aten::_efficient_attention_backward         0.03%     609.759us         0.22%       3.918ms     217.676us      29.266ms        12.45%      33.204ms       1.845ms            18            --  
fmha_cutlassB_f32_aligned_64x64_k32_sm80(PyTorchMemEffAttention::At...         0.00%       0.000us         0.00%       0.000us       0.000us      29.266ms        12.45%      29.266ms       1.626ms            18            --  
             autograd::engine::evaluate_function: ConvolutionBackward0         0.02%     417.513us         0.30%       5.254ms     175.131us       0.000us         0.00%      23.540ms     784.671us            30            --  
                                                  ConvolutionBackward0         0.01%     218.825us         0.28%       4.836ms     161.214us       0.000us         0.00%      23.540ms     784.671us            30            --  
                                            aten::convolution_backward         0.11%       1.911ms         0.26%       4.618ms     153.920us      22.816ms         9.70%      23.540ms     784.671us            30            --  
                                                           aten::fill_         1.36%      23.761ms         3.23%      56.414ms       9.450us      22.144ms         9.42%      22.145ms       3.709us          5970            --  
                                    aten::_native_multi_head_attention         0.26%       4.559ms         1.89%      32.978ms       1.099ms       0.000us         0.00%      21.798ms     726.615us            30            --  
void at::native::vectorized_elementwise_kernel<4, at::native::FillF...         0.00%       0.000us         0.00%       0.000us       0.000us      18.843ms         8.01%      18.843ms       5.965us          3159            --  
                                                           aten::copy_         0.42%       7.392ms         1.23%      21.553ms      18.807us      18.724ms         7.96%      18.724ms      16.338us          1146            --  
                                                              aten::mm         1.97%      34.391ms         2.24%      39.176ms      97.452us      18.436ms         7.84%      18.436ms      45.862us           402    650581.090  
                                                           aten::addmm         4.01%      70.043ms         4.23%      73.885ms     234.555us      17.792ms         7.57%      17.792ms      56.482us           315    303727.169  
                                                          aten::linear         0.15%       2.595ms         4.12%      71.857ms     237.150us       0.000us         0.00%      17.437ms      57.549us           303            --  
                                                           aten::clone         0.16%       2.707ms         1.45%      25.289ms      38.143us       0.000us         0.00%      16.995ms      25.634us           663            --  
                  autograd::engine::evaluate_function: SelectBackward0         0.04%     644.142us         0.29%       4.985ms      75.535us       0.000us         0.00%      14.534ms     220.216us            66            --  
                   autograd::engine::evaluate_function: AddmmBackward0         0.13%       2.327ms         1.92%      33.462ms     227.635us       0.000us         0.00%      14.420ms      98.094us           147            --  
```
