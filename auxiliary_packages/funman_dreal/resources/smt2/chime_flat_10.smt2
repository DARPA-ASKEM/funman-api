(set-logic QF_NRA)
(declare-fun s_0 () Real)
(declare-fun s_1 () Real)
(declare-fun s_2 () Real)
(declare-fun s_3 () Real)
(declare-fun s_4 () Real)
(declare-fun s_5 () Real)
(declare-fun s_6 () Real)
(declare-fun s_7 () Real)
(declare-fun s_8 () Real)
(declare-fun s_9 () Real)
(declare-fun s_10 () Real)
(declare-fun r_n_1 () Real)
(declare-fun r_n_2 () Real)
(declare-fun r_n_3 () Real)
(declare-fun r_n_4 () Real)
(declare-fun r_n_5 () Real)
(declare-fun r_n_6 () Real)
(declare-fun r_n_7 () Real)
(declare-fun r_n_8 () Real)
(declare-fun r_n_9 () Real)
(declare-fun r_n_10 () Real)
(declare-fun i_0 () Real)
(declare-fun i_1 () Real)
(declare-fun i_2 () Real)
(declare-fun i_3 () Real)
(declare-fun i_4 () Real)
(declare-fun i_5 () Real)
(declare-fun i_6 () Real)
(declare-fun i_7 () Real)
(declare-fun i_8 () Real)
(declare-fun i_9 () Real)
(declare-fun i_10 () Real)
(declare-fun scale_1 () Real)
(declare-fun scale_2 () Real)
(declare-fun scale_3 () Real)
(declare-fun scale_4 () Real)
(declare-fun scale_5 () Real)
(declare-fun scale_6 () Real)
(declare-fun scale_7 () Real)
(declare-fun scale_8 () Real)
(declare-fun scale_9 () Real)
(declare-fun scale_10 () Real)
(declare-fun r_0 () Real)
(declare-fun r_1 () Real)
(declare-fun r_2 () Real)
(declare-fun r_3 () Real)
(declare-fun r_4 () Real)
(declare-fun r_5 () Real)
(declare-fun r_6 () Real)
(declare-fun r_7 () Real)
(declare-fun r_8 () Real)
(declare-fun r_9 () Real)
(declare-fun r_10 () Real)
(declare-fun beta_0 () Real)
(declare-fun beta_1 () Real)
(declare-fun gamma () Real)
(declare-fun delta () Real)
(declare-fun n () Real)
(declare-fun s_n_1 () Real)
(declare-fun s_n_2 () Real)
(declare-fun s_n_3 () Real)
(declare-fun s_n_4 () Real)
(declare-fun s_n_5 () Real)
(declare-fun s_n_6 () Real)
(declare-fun s_n_7 () Real)
(declare-fun s_n_8 () Real)
(declare-fun s_n_9 () Real)
(declare-fun s_n_10 () Real)
(declare-fun i_n_1 () Real)
(declare-fun i_n_2 () Real)
(declare-fun i_n_3 () Real)
(declare-fun i_n_4 () Real)
(declare-fun i_n_5 () Real)
(declare-fun i_n_6 () Real)
(declare-fun i_n_7 () Real)
(declare-fun i_n_8 () Real)
(declare-fun i_n_9 () Real)
(declare-fun i_n_10 () Real)
(assert (and (and (= gamma 0.07142857142857142) (= delta 0.0) (= beta_0 6.7e-05) (= beta_1 6.7e-05)) (and (= s_0 1000.0) (= i_0 1.0) (= r_0 1.0) (= n (+ (+ s_0 i_0) r_0))) (and (and (and (= r_n_1 (+ (* gamma i_0) r_0)) (= s_n_1 (+ (* (* (* beta_0 (- 1.0)) s_0) i_0) s_0)) (= i_n_1 (+ (- (* (* beta_0 s_0) i_0) (* gamma i_0)) i_0)) (<= r_n_1 n) (<= 0.0 r_n_1) (<= s_n_1 n) (<= 0.0 s_n_1) (<= i_n_1 n) (<= 0.0 i_n_1)) (and (= scale_1 (/ n (+ (+ s_n_1 i_n_1) r_n_1))) (<= scale_1 1.0) (<= 0.0 scale_1)) (and (= s_1 (* s_n_1 scale_1)) (= i_1 (* i_n_1 scale_1)) (= r_1 (* r_n_1 scale_1)) (<= r_1 n) (<= 0.0 r_1) (<= s_1 n) (<= 0.0 s_1) (<= i_1 n) (<= 0.0 i_1))) (and (and (= r_n_2 (+ (* gamma i_1) r_1)) (= s_n_2 (+ (* (* (* beta_0 (- 1.0)) s_1) i_1) s_1)) (= i_n_2 (+ (- (* (* beta_0 s_1) i_1) (* gamma i_1)) i_1)) (<= r_n_2 n) (<= 0.0 r_n_2) (<= s_n_2 n) (<= 0.0 s_n_2) (<= i_n_2 n) (<= 0.0 i_n_2)) (and (= scale_2 (/ n (+ (+ s_n_2 i_n_2) r_n_2))) (<= scale_2 1.0) (<= 0.0 scale_2)) (and (= s_2 (* s_n_2 scale_2)) (= i_2 (* i_n_2 scale_2)) (= r_2 (* r_n_2 scale_2)) (<= r_2 n) (<= 0.0 r_2) (<= s_2 n) (<= 0.0 s_2) (<= i_2 n) (<= 0.0 i_2))) (and (and (= r_n_3 (+ (* gamma i_2) r_2)) (= s_n_3 (+ (* (* (* beta_0 (- 1.0)) s_2) i_2) s_2)) (= i_n_3 (+ (- (* (* beta_0 s_2) i_2) (* gamma i_2)) i_2)) (<= r_n_3 n) (<= 0.0 r_n_3) (<= s_n_3 n) (<= 0.0 s_n_3) (<= i_n_3 n) (<= 0.0 i_n_3)) (and (= scale_3 (/ n (+ (+ s_n_3 i_n_3) r_n_3))) (<= scale_3 1.0) (<= 0.0 scale_3)) (and (= s_3 (* s_n_3 scale_3)) (= i_3 (* i_n_3 scale_3)) (= r_3 (* r_n_3 scale_3)) (<= r_3 n) (<= 0.0 r_3) (<= s_3 n) (<= 0.0 s_3) (<= i_3 n) (<= 0.0 i_3))) (and (and (= r_n_4 (+ (* gamma i_3) r_3)) (= s_n_4 (+ (* (* (* beta_0 (- 1.0)) s_3) i_3) s_3)) (= i_n_4 (+ (- (* (* beta_0 s_3) i_3) (* gamma i_3)) i_3)) (<= r_n_4 n) (<= 0.0 r_n_4) (<= s_n_4 n) (<= 0.0 s_n_4) (<= i_n_4 n) (<= 0.0 i_n_4)) (and (= scale_4 (/ n (+ (+ s_n_4 i_n_4) r_n_4))) (<= scale_4 1.0) (<= 0.0 scale_4)) (and (= s_4 (* s_n_4 scale_4)) (= i_4 (* i_n_4 scale_4)) (= r_4 (* r_n_4 scale_4)) (<= r_4 n) (<= 0.0 r_4) (<= s_4 n) (<= 0.0 s_4) (<= i_4 n) (<= 0.0 i_4))) (and (and (= r_n_5 (+ (* gamma i_4) r_4)) (= s_n_5 (+ (* (* (* beta_0 (- 1.0)) s_4) i_4) s_4)) (= i_n_5 (+ (- (* (* beta_0 s_4) i_4) (* gamma i_4)) i_4)) (<= r_n_5 n) (<= 0.0 r_n_5) (<= s_n_5 n) (<= 0.0 s_n_5) (<= i_n_5 n) (<= 0.0 i_n_5)) (and (= scale_5 (/ n (+ (+ s_n_5 i_n_5) r_n_5))) (<= scale_5 1.0) (<= 0.0 scale_5)) (and (= s_5 (* s_n_5 scale_5)) (= i_5 (* i_n_5 scale_5)) (= r_5 (* r_n_5 scale_5)) (<= r_5 n) (<= 0.0 r_5) (<= s_5 n) (<= 0.0 s_5) (<= i_5 n) (<= 0.0 i_5))) (and (and (= r_n_6 (+ (* gamma i_5) r_5)) (= s_n_6 (+ (* (* (* beta_0 (- 1.0)) s_5) i_5) s_5)) (= i_n_6 (+ (- (* (* beta_0 s_5) i_5) (* gamma i_5)) i_5)) (<= r_n_6 n) (<= 0.0 r_n_6) (<= s_n_6 n) (<= 0.0 s_n_6) (<= i_n_6 n) (<= 0.0 i_n_6)) (and (= scale_6 (/ n (+ (+ s_n_6 i_n_6) r_n_6))) (<= scale_6 1.0) (<= 0.0 scale_6)) (and (= s_6 (* s_n_6 scale_6)) (= i_6 (* i_n_6 scale_6)) (= r_6 (* r_n_6 scale_6)) (<= r_6 n) (<= 0.0 r_6) (<= s_6 n) (<= 0.0 s_6) (<= i_6 n) (<= 0.0 i_6))) (and (and (= r_n_7 (+ (* gamma i_6) r_6)) (= s_n_7 (+ (* (* (* beta_0 (- 1.0)) s_6) i_6) s_6)) (= i_n_7 (+ (- (* (* beta_0 s_6) i_6) (* gamma i_6)) i_6)) (<= r_n_7 n) (<= 0.0 r_n_7) (<= s_n_7 n) (<= 0.0 s_n_7) (<= i_n_7 n) (<= 0.0 i_n_7)) (and (= scale_7 (/ n (+ (+ s_n_7 i_n_7) r_n_7))) (<= scale_7 1.0) (<= 0.0 scale_7)) (and (= s_7 (* s_n_7 scale_7)) (= i_7 (* i_n_7 scale_7)) (= r_7 (* r_n_7 scale_7)) (<= r_7 n) (<= 0.0 r_7) (<= s_7 n) (<= 0.0 s_7) (<= i_7 n) (<= 0.0 i_7))) (and (and (= r_n_8 (+ (* gamma i_7) r_7)) (= s_n_8 (+ (* (* (* beta_0 (- 1.0)) s_7) i_7) s_7)) (= i_n_8 (+ (- (* (* beta_0 s_7) i_7) (* gamma i_7)) i_7)) (<= r_n_8 n) (<= 0.0 r_n_8) (<= s_n_8 n) (<= 0.0 s_n_8) (<= i_n_8 n) (<= 0.0 i_n_8)) (and (= scale_8 (/ n (+ (+ s_n_8 i_n_8) r_n_8))) (<= scale_8 1.0) (<= 0.0 scale_8)) (and (= s_8 (* s_n_8 scale_8)) (= i_8 (* i_n_8 scale_8)) (= r_8 (* r_n_8 scale_8)) (<= r_8 n) (<= 0.0 r_8) (<= s_8 n) (<= 0.0 s_8) (<= i_8 n) (<= 0.0 i_8))) (and (and (= r_n_9 (+ (* gamma i_8) r_8)) (= s_n_9 (+ (* (* (* beta_0 (- 1.0)) s_8) i_8) s_8)) (= i_n_9 (+ (- (* (* beta_0 s_8) i_8) (* gamma i_8)) i_8)) (<= r_n_9 n) (<= 0.0 r_n_9) (<= s_n_9 n) (<= 0.0 s_n_9) (<= i_n_9 n) (<= 0.0 i_n_9)) (and (= scale_9 (/ n (+ (+ s_n_9 i_n_9) r_n_9))) (<= scale_9 1.0) (<= 0.0 scale_9)) (and (= s_9 (* s_n_9 scale_9)) (= i_9 (* i_n_9 scale_9)) (= r_9 (* r_n_9 scale_9)) (<= r_9 n) (<= 0.0 r_9) (<= s_9 n) (<= 0.0 s_9) (<= i_9 n) (<= 0.0 i_9))) (and (and (= r_n_10 (+ (* gamma i_9) r_9)) (= s_n_10 (+ (* (* (* beta_0 (- 1.0)) s_9) i_9) s_9)) (= i_n_10 (+ (- (* (* beta_0 s_9) i_9) (* gamma i_9)) i_9)) (<= r_n_10 n) (<= 0.0 r_n_10) (<= s_n_10 n) (<= 0.0 s_n_10) (<= i_n_10 n) (<= 0.0 i_n_10)) (and (= scale_10 (/ n (+ (+ s_n_10 i_n_10) r_n_10))) (<= scale_10 1.0) (<= 0.0 scale_10)) (and (= s_10 (* s_n_10 scale_10)) (= i_10 (* i_n_10 scale_10)) (= r_10 (* r_n_10 scale_10)) (<= r_10 n) (<= 0.0 r_10) (<= s_10 n) (<= 0.0 s_10) (<= i_10 n) (<= 0.0 i_10)))) (and (< i_0 (* n 0.01)) (< i_1 (* n 0.01)) (< i_2 (* n 0.01)) (< i_3 (* n 0.01)) (< i_4 (* n 0.01)) (< i_5 (* n 0.01)) (< i_6 (* n 0.01)) (< i_7 (* n 0.01)) (< i_8 (* n 0.01)) (< i_9 (* n 0.01)) (< i_10 (* n 0.01)))))
(check-sat)
