# Reference verification (revised manuscript)

Every entry of the bibliography of `paper/main.tex` was checked against its record at an
authoritative source: the publisher or proceedings page (IEEE Xplore, ACM DL, PMLR, CVF Open
Access, NeurIPS proceedings, OpenReview, JMLR, PNAS/PubMed, Project Euclid, JSTOR, Taylor &
Francis, Cell), the arXiv abstract page, the 3GPP/ETSI specification record, with DBLP as a
cross-check of authors, venue and year.

Method and its limits. Direct page fetches from the session were refused by its network policy
for dblp.org, api.crossref.org, proceedings.mlr.press and export.arxiv.org, so the fields were
confirmed from search results restricted to the domains above. Fields that rest only on
secondary records are marked below; nothing was filled from memory.

## Corrections made against the submitted bibliography

| Entry | Correction |
|---|---|
| CRC-8 polynomial | The polynomial used, D^8+D^7+D^4+D^3+D+1 (`citadel_rx/coding/crc.py`, 0x9B), is gCRC8 of 3GPP TS 36.212 (E-UTRA) Sec. 5.1.1; TS 38.212 (NR) defines CRC-24A/B/C, CRC-16, CRC-11 and CRC-6 only. The citation now points to TS 36.212 (seen as ETSI TS 136 212 V19.1.0, 2025-10). |
| Titans | Now published: NeurIPS 2025 (vol. 38); arXiv:2501.00663 kept. |
| Nested learning | Confirmed NeurIPS 2025 (vol. 38), arXiv:2512.24695. |
| Wu et al. 2024 | arXiv only (2409.02430); no journal or conference version found. The arXiv title spells "Receviers"; it is reproduced as in the source. |
| Wu et al. 2023 (TTA risks) | PMLR vol. 202, pp. 37456-37495 added. |
| MedBN | CVPR 2024, pp. 5997-6007 added. |
| Blanchard et al. 2017 | pp. 119-129 (NeurIPS 30 as indexed by DBLP; the ACM edition prints 118-128). |
| Steinhardt et al. 2017 | pp. 3517-3529 (DBLP). |
| Code-verified training | ViterbiNet (IEEE TWC 2020) re-trains on decoded and re-encoded codewords when decoding succeeds; Schibisch et al. (ISWCS 2018), whose training set "contains only the correctly received symbols ... (e.g., due to a cyclic redundancy check (CRC))", is cited with it. |
| McClelland et al. 1995 | Full title with its subtitle. |

## New entries (all verified)

Zhou, Maham, Hjorungnes, IEEE TWC 11(3):903-907, 2012; Kapetanovic, Zheng, Rusek, IEEE Commun.
Mag. 53(6):21-27, 2015; Kapetanovic, Zheng, Wong, Ottersten, PIMRC 2013, pp. 13-18; Tugnait,
IEEE WCL 4(5):525-528, 2015 (DOI from citing records); Shlezinger, Farsad, Eldar, Goldsmith, IEEE
TWC 19(5):3319-3331, 2020; Schibisch et al., ISWCS 2018, pp. 1-5; Niu et al. (EATA), ICML 2022,
PMLR 162:16888-16905; Wang, Fink, Van Gool, Dai (CoTTA), CVPR 2022, pp. 7201-7211; Niu et al.
(SAR), ICLR 2023; Yuan, Xie, Li (RoTTA), CVPR 2023, pp. 15922-15932; Hoang, Vo, Do, NeurIPS 2024
(vol. 37; pages not confirmed); Li, Grandvalet, Davoine (L2-SP), ICML 2018, PMLR 80:2825-2834
(PMLR pagination); Kirkpatrick et al. (EWC), PNAS 114(13):3521-3526, 2017 (all 14 authors);
Tarvainen, Valpola, NeurIPS 30, pp. 1195-1204; Athalye, Carlini, Wagner (BPDA, Sec. 4.1), ICML
2018, PMLR 80:274-283; Athalye, Engstrom, Ilyas, Kwok (EOT), ICML 2018, PMLR 80:284-293; Tramer,
Carlini, Brendel, Madry, NeurIPS 33, pp. 1633-1645; Carlini et al., arXiv:1902.06705 (9 authors in
v2); Ilyas, Engstrom, Athalye, Lin, ICML 2018, PMLR 80:2137-2146; Wierstra et al., JMLR 15(27):
949-980, 2014; Sadeghi, Larsson, IEEE WCL 8(1):213-216, 2019; McClelland, McNaughton, O'Reilly,
Psychol. Rev. 102(3):419-457, 1995; Kumaran, Hassabis, McClelland, Trends Cogn. Sci. 20(7):
512-534, 2016; Kunsch, Ann. Statist. 17(3):1217-1241, 1989; Wilson, JASA 22(158):209-212, 1927;
Huber, Ann. Math. Statist. 35(1):73-101, 1964; 3GPP TR 38.901 V19.5.0 Table 7.4.1-1
(UMi-Street Canyon LOS: PL1 = 32.4 + 21 log10(d3D) + 20 log10(fc) below the breakpoint).

## Added in the second revision campaign

3GPP TS 38.212 "NR; Multiplexing and channel coding", V19.2.0 (2025-12): Sec. 5.1 CRC calculation,
Sec. 5.3.2 low density parity check coding (table of contents of the 3GPP draft record). The code
blocks of the coded scene are built by Sionna PHY 2.2 (`LDPC5GEncoder`, `CRCEncoder("CRC24A")`).

Sionna: cited as the software record its authors ask for, copied from the citation block of the
installed package's metadata (`sionna-no-rt` 2.2.0, `importlib.metadata ... METADATA`): `@software{sionna,
title = {Sionna}, author = {Hoydis, Jakob and Cammerer, Sebastian and {Ait Aoudia}, Fayçal and
Nimier-David, Merlin and Maggi, Lorenzo and Marcus, Guillermo and Vem, Avinash and Keller, Alexander},
note = {https://nvlabs.github.io/sionna/}, year = {2022}, version = {2.2.0}}`. The UMi drops use
`sionna.phy.channel.tr38901.UMi` of the same package.

3GPP TS 38.211 "NR; Physical channels and modulation", Sec. 5.2.1 (length-31 Gold sequence,
N_c = 1600) and Sec. 6.3.1.1 (PUSCH scrambling, c_init = n_RNTI 2^15 + n_ID): the section numbers and
the initialisation are those of Sionna's implementation (`sionna/phy/nr/utils.py::generate_prng_seq`,
`sionna/phy/fec/scrambling.py::TB5GScrambler`), which the code uses. The version
now given in the bibliography (V19.2.0, ETSI record of Feb. 2026) is documented in the third check below.

## Items to check once by eye before submission

* TR 38.901 V19.5.0, Table 7.4.1-1: the extracted PDF text was partly garbled; the coefficients
  (21 log10 d below the breakpoint) match every earlier version seen (V14-V17).
* Mokhtari et al. (CDC 2016, pp. 7195-7201) and Samuel et al. (DOI) rest on secondary records;
  Mokhtari et al. is no longer cited in the revision.

## Third check (pre-submission)

An independent audit re-checked every bibliography entry and every sentence that attributes something to
a reference, and a second reviewer confirmed each finding before it was applied. Limits of this check,
stated plainly: every record below was confirmed from search results on the authoritative domains (titles,
snippets and abstracts returned for those domains), not from opened pages, with one exception: pypi.org was
fetched directly (the Sionna release date). arxiv.org, 3gpp.org, etsi.org, ieeexplore.ieee.org, dblp.org,
proceedings.mlr.press, github.com (third-party repositories) and weizmann.ac.il are outside the network
domains this machine may reach, so no publisher, arXiv or standards page was opened. No field was filled from
memory, and a field that no record showed was left out of the entry.

### Corrections to existing entries

* `ts38211`: The only 3GPP entry without version or date, although the paper quotes clause numbers from it. Entry now: 3GPP, ``NR; Physical channels and modulation,'' TS 38.211, V19.2.0 (ETSI TS 138 211 V19.2.0, Feb. 2026), Secs. 5.2.1 and 6.3.1.1.
  Source: https://www.3gpp.org/dynareport/38211.htm (search result: RAN#110, version 19.2.0, uploaded 2026-01-15; 19.5.0 uploaded 2026-09-24) ; https://www.etsi.org/deliver/etsi_ts/138200_138299/138211/19.02.00_60/ts_138211v190200p.pdf (search result title: 'ETSI TS 138 211 V19.2.0 (2026-02) 5G; NR; Physical channels and modulation')
  Note: Confirmed from search results on 3gpp.org and etsi.org; neither host can be fetched from this machine. V19.2.0 is the version of the same plenary as the cited TS 38.212 V19.2.0. The 3GPP cover date of TS 38.211 V19.2.0 was NOT seen (the one indexed 3GPP draft file has a garbled cover), so the entry gives the ETSI record, which was seen. If the author reads the 3GPP cover and it says 2025-12, the entry can be written as the others: 'TS 38.211, V19.2.0, 2025, Secs. 5.2.1 and 6.3.1.1.' Clause numbers 5.2.1 and 6.3.1.1 were not read in V19.2.0 itself; they are those of earlier releases (Release 16 to 18 documentation) and of the Sionna 2.2.0 source the code uses.
* `sionna`: 'version 2.2.0, 2022' reads as a 2022 release. 2022 is the year of the citation block the authors ask for; version 2.2.0 was released in September 2026. Entry now: J.~Hoydis, S.~Cammerer, F.~Ait Aoudia, M.~Nimier-David, L.~Maggi, G.~Marcus, A.~Vem, and A.~Keller, ``Sionna,'' software, 2022; version 2.2.0, Sep. 2026. [Online]. Available: \url{https://nvlabs.github.io/sionna/}
  Source: https://pypi.org/pypi/sionna/2.2.0/json (fetched directly: version 2.2.0, upload_time 2026-09-29) ; citation block in the metadata of the installed package sionna-no-rt 2.2.0 (eight authors in this order, title 'Sionna', year 2022, version 2.2.0, note https://nvlabs.github.io/sionna/)
  Note: Authors, title and URL match the software's own citation block; only the pairing of year and version changes.

### New entries

* `raviv2024` (finding ref-raviv2023-ack): T.~Raviv, S.~Park, O.~Simeone, Y.~C. Eldar, and N.~Shlezinger, ``Adaptive and flexible model-based AI for deep receivers in dynamic channels,'' \emph{IEEE Wireless Commun.}, vol.~31, no.~4, pp. 163--169, 2024.
  Source: https://arxiv.org/abs/2305.07309 (search extract naming the repository as the paper's source code) ; https://cris.bgu.ac.il/en/publications/adaptive-and-flexible-model-based-ai-for-deep-receivers-in-dynami/ and https://cris.iucc.ac.il/en/publications/adaptive-and-flexible-model-based-ai-for-deep-receivers-in-dynami/ (IEEE Wireless Commun., vol. 31, no. 4, pp. 163-169, 2024, DOI 10.1109/MWC.012.2300242)
  Note: New entry; place it directly after \bibitem{liu2012cost} (the list is not in strict order of first citation; if it is renumbered, raviv2024 is first cited in Table tab:hyper). 'Aug.' is inferred from the issue number of a bimonthly magazine (no. 6 is December in the liu2012cost entry) and was not seen on a record. In Table tab:setup (l.586) 'COST2100 traces of \cite{raviv2023,liu2012cost}' may stay: Raviv et al. 2023 do evaluate a COST 2100 channel.
* `uzlaner2024` (finding prior-8): N.~Uzlaner, T.~Raviv, N.~Shlezinger, and K.~Todros, ``Asynchronous online adaptation via modular drift detection for deep receivers,'' arXiv:2407.09134, Jul. 2024.
  Source: https://arxiv.org/abs/2407.09134 (search result: N. Uzlaner, T. Raviv, N. Shlezinger, K. Todros, submitted 12 Jul 2024; drift detection to decide when a deep receiver is re-trained, and a modular variant that decides which sub-module) ; https://cris.iucc.ac.il/en/publications/asynchronous-online-adaptation-via-modular-drift-detection-for-de/ (IEEE Trans. Wireless Commun., 'accepted/in press', no volume or pages)
  Note: Cited as the arXiv record, which is the only one confirmed; the IEEE TWC volume and pages were not found. Place the entry after \bibitem{schibisch2018} (first citation is the sentence added by prior-8b; if prior-8b is not applied, the first citation is l.605 and the entry goes after \bibitem{cotta2022} in citation order).
* `gusakov2025` (finding prior-8b): Y.~Gusakov, O.~Simeone, T.~Routtenberg, and N.~Shlezinger, ``Online learning of modular Bayesian deep receivers: Single-step adaptation with streaming data,'' arXiv:2511.06045, Nov. 2025.
  Source: https://arxiv.org/abs/2407.09134 (as above) ; https://arxiv.org/abs/2511.06045 (search result: Y. Gusakov, O. Simeone, T. Routtenberg, N. Shlezinger, submitted 8 Nov 2025; online training as Bayesian tracking of the network parameters, single-step adaptation in place of multi-epoch gradient descent, one localised Bayesian update per module)
  Note: gusakov2025 goes directly after uzlaner2024. A repository lists a version in press in IEEE Trans. Signal Process. (DOI 10.1109/TSP.2026.3697255); that record was not confirmed, so the arXiv record is cited.
* `cong2024` (finding prior-10): T.~Cong, X.~He, Y.~Shen, and Y.~Zhang, ``Test-time poisoning attacks against test-time adaptation models,'' in \emph{Proc. IEEE Symp. Secur. Privacy (SP)}, 2024, pp. 1306--1324.
  Source: https://dblp.org/rec/conf/sp/CongHSZ24 and https://ieeexplore.ieee.org/document/10646694/ (search result: SP 2024, pp. 1306-1324; arXiv:2308.08505) ; https://proceedings.iclr.cc/paper_files/paper/2025/hash/bb309cc1fbdb88ea755bd7cee4b310ec-Abstract-Conference.html (seven authors; abstract: under realistic assumptions, without the real-time weights and other users' benign samples, TTA methods are more robust than previously believed; arXiv:2410.04682) ; https://neurips.cc/virtual/2023/poster/71448 and https://arxiv.org/abs/2306.05401 (abstract: RDumb periodically resets the model to its pre-trained state and is better than or on par with the state of the art on all benchmarks considered)
  Note: cong2024 and su2025 go after \bibitem{wu2023tta}; rdumb2023 after \bibitem{medbn}. Initials of Su et al. from the ICLR record: Yongyi Su, Yushu Li, Nanqing Liu, Kui Jia, Xulei Yang, Chuan-Sheng Foo, Xun Xu. NeurIPS 2023 is volume 36 of the proceedings (the volume label was not seen on the RDumb page itself; the paper prints no pages for vol. 37 and 38 either).
* `su2025` (finding prior-10): Y.~Su, Y.~Li, N.~Liu, K.~Jia, X.~Yang, C.-S. Foo, and X.~Xu, ``On the adversarial risk of test time adaptation: An investigation into realistic test-time data poisoning,'' in \emph{Proc. Int. Conf. Learn. Represent. (ICLR)}, 2025.
  Source: https://dblp.org/rec/conf/sp/CongHSZ24 and https://ieeexplore.ieee.org/document/10646694/ (search result: SP 2024, pp. 1306-1324; arXiv:2308.08505) ; https://proceedings.iclr.cc/paper_files/paper/2025/hash/bb309cc1fbdb88ea755bd7cee4b310ec-Abstract-Conference.html (seven authors; abstract: under realistic assumptions, without the real-time weights and other users' benign samples, TTA methods are more robust than previously believed; arXiv:2410.04682) ; https://neurips.cc/virtual/2023/poster/71448 and https://arxiv.org/abs/2306.05401 (abstract: RDumb periodically resets the model to its pre-trained state and is better than or on par with the state of the art on all benchmarks considered)
  Note: cong2024 and su2025 go after \bibitem{wu2023tta}; rdumb2023 after \bibitem{medbn}. Initials of Su et al. from the ICLR record: Yongyi Su, Yushu Li, Nanqing Liu, Kui Jia, Xulei Yang, Chuan-Sheng Foo, Xun Xu. NeurIPS 2023 is volume 36 of the proceedings (the volume label was not seen on the RDumb page itself; the paper prints no pages for vol. 37 and 38 either).
* `rdumb2023` (finding prior-10): O.~Press, S.~Schneider, M.~K{\"u}mmerer, and M.~Bethge, ``RDumb: A simple approach that questions our progress in continual test-time adaptation,'' in \emph{Adv. Neural Inf. Process. Syst. (NeurIPS)}, 2023.
  Source: https://dblp.org/rec/conf/sp/CongHSZ24 and https://ieeexplore.ieee.org/document/10646694/ (search result: SP 2024, pp. 1306-1324; arXiv:2308.08505) ; https://proceedings.iclr.cc/paper_files/paper/2025/hash/bb309cc1fbdb88ea755bd7cee4b310ec-Abstract-Conference.html (seven authors; abstract: under realistic assumptions, without the real-time weights and other users' benign samples, TTA methods are more robust than previously believed; arXiv:2410.04682) ; https://neurips.cc/virtual/2023/poster/71448 and https://arxiv.org/abs/2306.05401 (abstract: RDumb periodically resets the model to its pre-trained state and is better than or on par with the state of the art on all benchmarks considered)
  Note: cong2024 and su2025 go after \bibitem{wu2023tta}; rdumb2023 after \bibitem{medbn}. Initials of Su et al. from the ICLR record: Yongyi Su, Yushu Li, Nanqing Liu, Kui Jia, Xulei Yang, Chuan-Sheng Foo, Xun Xu. NeurIPS 2023 is volume 36 of the proceedings (the volume label was not seen on the RDumb page itself; the paper prints no pages for vol. 37 and 38 either).
* `hu2026` (finding prior-11): Y.~Hu and L.~Duan, ``Theory of continual learning against data poisoning attacks,'' in \emph{Proc. 43rd Int. Conf. Mach. Learn. (ICML)}, PMLR vol.~306, 2026, pp. 44906--44935.
  Source: https://proceedings.mlr.press/v306/hu26n.html (search result: Yiting Hu, Lingjie Duan, Proc. 43rd ICML, PMLR 306:44906-44935, 2026) ; https://icml.cc/virtual/2026/poster/65304 (summary: one defence compares consecutive learning updates to detect suspicious tasks) ; https://arxiv.org/abs/2606.29841
  Note: Goes after \bibitem{steinhardt2017}. Record and abstract from search results on proceedings.mlr.press and icml.cc (not fetchable here); the paper itself was not read, so the description is limited to what the abstract states.
* `sadeghi2019ae` (finding prior-9): M.~Sadeghi and E.~G. Larsson, ``Physical adversarial attacks against end-to-end autoencoder communication systems,'' \emph{IEEE Commun. Lett.}, vol.~23, no.~5, pp. 847--850, May 2019.
  Source: https://arxiv.org/abs/1902.08391 and https://peeref.com/works/18396597 (IEEE Commun. Lett., vol. 23, no. 5, pp. 847-850, May 2019, DOI 10.1109/LCOMM.2019.2901469; abstract: physical black-box attacks on autoencoder links, more destructive than jamming) ; https://dblp.org/rec/journals/tmc/SagduyuSE21.html (IEEE Trans. Mob. Comput. 20(2): 306-319, 2021; DOI 10.1109/TMC.2019.2950398) and https://arxiv.org/abs/1911.00500 (abstract: the adversary transmits in the sensing period to manipulate the transmitter's test inputs and its re-training data)
  Note: Both entries go after \bibitem{sadeghi2019}, in this order. The Sadeghi-Larsson letter rests on arXiv plus secondary indexes (IEEE Xplore not reachable). For Sagduyu et al. the journal record is confirmed on DBLP; 'Feb.' is inferred from issue no. 2 of a monthly journal.
* `sagduyu2021` (finding prior-9): Y.~E. Sagduyu, Y.~Shi, and T.~Erpek, ``Adversarial deep learning for over-the-air spectrum poisoning attacks,'' \emph{IEEE Trans. Mobile Comput.}, vol.~20, no.~2, pp. 306--319, 2021.
  Source: https://arxiv.org/abs/1902.08391 and https://peeref.com/works/18396597 (IEEE Commun. Lett., vol. 23, no. 5, pp. 847-850, May 2019, DOI 10.1109/LCOMM.2019.2901469; abstract: physical black-box attacks on autoencoder links, more destructive than jamming) ; https://dblp.org/rec/journals/tmc/SagduyuSE21.html (IEEE Trans. Mob. Comput. 20(2): 306-319, 2021; DOI 10.1109/TMC.2019.2950398) and https://arxiv.org/abs/1911.00500 (abstract: the adversary transmits in the sensing period to manipulate the transmitter's test inputs and its re-training data)
  Note: Both entries go after \bibitem{sadeghi2019}, in this order. The Sadeghi-Larsson letter rests on arXiv plus secondary indexes (IEEE Xplore not reachable). For Sagduyu et al. the journal record is confirmed on DBLP; 'Feb.' is inferred from issue no. 2 of a monthly journal.

Three fields proposed by the audit were inferred, were seen on no record, and are therefore NOT printed:
the month ("Aug.") of `raviv2024` (inferred from issue no. 4 of a bimonthly magazine), the month ("Feb.") of
`sagduyu2021` (inferred from issue no. 2 of a monthly journal) and the volume ("vol. 36") of `rdumb2023`
(the NeurIPS 2023 volume number, not seen on the paper's page). Add them once read on the publisher page.
`uzlaner2024` and `gusakov2025` are cited as arXiv preprints: journal versions (IEEE Trans. Wireless Commun.;
IEEE Trans. Signal Process.) are listed as in press by repositories and were not confirmed.

### Corrections to what the text attributes to a reference

* ref-wu2024 (l. 88-92 (same finding as prior-1) of the pre-audit file): Four things are credited to Wu et al. that could not be found in any indexed text of arXiv:2409.02430 and that the project's own notes mark as unverified: the unrolled adaptation step, 'an order of magnitude', a surrogate result 'still' transferring (which implies a white-box result in that paper; its attack is transfer-based throughout), and Meta-DeepSIC not recovering after the attack stops (the project's own observation, docs/RESEARCH_NOTES.md l.112, main.tex l.717-719). Confirmed content of the paper: perturbations injected into the pilots without knowledge of the target, crafted with PGD on a surrogate model, evaluated on DeepSIC, Meta-DeepSIC, a black-box DNN detector and a ResNet detector over synthetic linear, non-linear, static and COST 2100 channels.
  Source: https://arxiv.org/abs/2409.02430 and https://arxiv.org/html/2409.02430v3 (search results only; arxiv.org cannot be fetched from this machine): abstract ('without knowledge of the attack target', perturbations injected into the pilots), HTML extract ('employ the projected gradient descent (PGD) algorithm to generate the adversarial poisoning attack perturbations'; surrogate built by federated learning in v1/v2, joint learning in v3; DeepSIC, Meta-DeepSIC, black-box DNN detector, ResNet detector)
* ref-wu2024-budget (l. 247 of the pre-audit file): 'as in \cite{wu2024}' asserts that Wu et al. set the budget relative to the received pilot energy, noise included. Not found in any indexed text of the paper; the project's notes record an absolute per-symbol budget read from it and mark that reading as unverified.
  Source: https://arxiv.org/abs/2409.02430 (search results; no extract defines the budget); /home/user/Citradel-Rx/docs/RESEARCH_NOTES.md l.56-62
* ref-wu2024-hyper (l. 485 of the pre-audit file): In a column headed 'Value; provenance' the cite presents 20 PGD steps of 0.25 epsilon through 2 unrolled steps as the configuration of Wu et al. These are this paper's settings; only the use of PGD on a surrogate is confirmed for Wu et al.
  Source: https://arxiv.org/html/2409.02430v3 (search extract: PGD); /home/user/Citradel-Rx/citadel_rx/attacks/pilot_poisoning.py
* ref-wu2024-setup (l. 590 of the pre-audit file): Same attribution in Table tab:setup: the unrolled steps are cited to Wu et al. and Madry et al.; neither is confirmed to unroll an adaptation step.
  Source: https://arxiv.org/html/2409.02430v3 (search extract: PGD on a surrogate)
* ref-shlezinger2021-raviv2023-intro (l. 81-85 (same finding as prior-2) of the pre-audit file): The Introduction says Meta-DeepSIC meta-learns 'from the pilots of past blocks' and that the adaptation data of both receivers are pilots. Raviv et al. state that the method 'does not require transmission of new pilot data for training': a successfully decoded codeword is re-encoded and used as training data. Per-block pilot training is the form attacked by Wu et al. ('online learning ... with over-the-air data (e.g., pilots)') and implemented here.
  Source: https://arxiv.org/abs/2203.14359 and https://researchwith.njit.edu/en/publications/online-meta-learning-for-hybrid-model-based-deep-receivers/ (abstract: 'does not require transmission of new pilot data for training'; preprint extract: a successfully decoded codeword is re-encoded as new training data, and the update runs only when the decoder reports a correct decode) ; https://arxiv.org/abs/2409.02430 (abstract: over-the-air data, e.g. pilots) ; https://arxiv.org/abs/2002.03214 (search extract: small training sets make DeepSIC suitable for online training; block-fading evaluation in Sec. IV-D)
* ref-shlezinger2021-table (l. 113, 121-122 of the pre-audit file): Table I lists online DeepSIC and Meta-DeepSIC with attack surface 'pilots' and a 'pilot buffer'; that is the pilot-trained form of Wu et al., not the form in which Meta-DeepSIC was proposed.
  Source: as for ref-shlezinger2021-raviv2023-intro
* ref-viterbinet2020 (l. 136-139 of the pre-audit file): Code-verified decision-directed training is presented as a precedent found in ViterbiNet and Schibisch et al. only; Meta-DeepSIC, one of the two receivers the paper defends, was proposed with it.
  Source: https://arxiv.org/abs/2203.14359 (search extract: re-encoding of a successfully decoded codeword as training data; update only on a correct decode)
* ref-raviv2023-buffer (l. 238-239 of the pre-audit file): 'a buffer of the last 20 pilot blocks, refreshed every five blocks \cite{raviv2023}' places the cite on settings that are this paper's (the 20-block pilot buffer; Raviv et al. need no new pilots). Move the cite to the method.
  Source: https://arxiv.org/abs/2203.14359 (abstract, via search); /home/user/Citradel-Rx/docs/RESEARCH_NOTES.md l.46-48
* ref-shlezinger2021-hyper (l. 472 of the pre-audit file): The provenance column credits Q=3, width 64 times the constellation order, 300 steps, step size 5e-3 and Adam to the DeepSIC paper. The project's record traces them to the public PyTorch repository tomerraviv95/facilitating-adaptation-deep-receivers (docs/RESEARCH_NOTES.md l.42-53), which is the code released with Raviv et al., IEEE Wireless Commun. 2024 (the paper names that repository as its source code).
  Source: https://arxiv.org/abs/2305.07309 (search extract of the paper: 'The source code used in our experiments is available at https://github.com/tomerraviv95/facilitating-adaptation-deep-receivers') ; https://cris.bgu.ac.il/en/publications/adaptive-and-flexible-model-based-ai-for-deep-receivers-in-dynami/ (IEEE Wireless Commun. 31(4):163-169, 2024, DOI 10.1109/MWC.012.2300242)
* ref-raviv2023-ack (l. 1372 of the pre-audit file): The Acknowledgment says the COST2100 traces were 'released with \cite{raviv2023}'. README.md and docs/RESEARCH_NOTES.md record that they are the files of the repository tomerraviv95/facilitating-adaptation-deep-receivers, which is the code of a different paper by the same five authors (IEEE Wireless Commun., 2024). NOT applied to the Acknowledgment (the author decides its wording; proposed sentence: "The COST2100 traces and the DeepSIC reference settings of Table~\ref{tab:hyper} are those of the public code released with \cite{raviv2024}, \url{https://github.com/tomerraviv95/facilitating-adaptation-deep-receivers}."); only the entry `raviv2024` was added.
  Source: https://arxiv.org/abs/2305.07309 (search extract naming the repository as the paper's source code) ; https://cris.bgu.ac.il/en/publications/adaptive-and-flexible-model-based-ai-for-deep-receivers-in-dynami/ and https://cris.iucc.ac.il/en/publications/adaptive-and-flexible-model-based-ai-for-deep-receivers-in-dynami/ (IEEE Wireless Commun., vol. 31, no. 4, pp. 163-169, 2024, DOI 10.1109/MWC.012.2300242)
* ref-oshea2017 (l. 78 of the pre-audit file): The opening sentence cites [1]-[4] for networks inside 'a MIMO detector'. O'Shea and Hoydis treat the link as an autoencoder and DeepRx is an OFDM receiver; 'MIMO detector' fits only DetNet [3].
  Source: Titles and abstracts of the entries as verified by the first audit (IEEE TCCN 3(4):563-575; IEEE TWC 20(6):3925-3940)
* ref-zhou2012pilot (l. 120 of the pre-audit file): Table I cites Zhou et al. in the row 'Pilot-spoofing detection ... detection only'. The letter derives the pilot contamination attack of an active eavesdropper and proposes no detector; the running text (l.135-136) cites it correctly as the threat.
  Source: https://researchportalplus.anu.edu.au/en/publications/pilot-contamination-for-active-eavesdropping/ ; https://www.scilit.net/publications/bf1ab81779f1d14a4ef7632ca3cd9289 (abstract via search: the eavesdropper attacks the training phase so that the precoder favours its own reception; a full-duplex variant; no detection scheme)
* ref-sar2023 (l. 142-143 (same finding as prior-6 and ref-persistent2024) of the pre-audit file): 'these methods assume i.i.d. batches' is false for three works cited in the sentence: SAR addresses mixed shifts, small batches and online imbalanced label shift; RoTTA addresses test samples correlated over time; PeTTA addresses recurring environments. 'are compared below in receiver form' is also too wide: no SAR, RoTTA or PeTTA receiver is among the baselines.
  Source: https://iclr.cc/virtual/2023/poster/12131 (SAR abstract) ; https://openaccess.thecvf.com/content/CVPR2023/html/Yuan_Robust_Test-Time_Adaptation_in_Dynamic_Scenarios_CVPR_2023_paper.html (RoTTA abstract: previous methods succeed on independently sampled data; test samples correlated over time) ; https://papers.nips.cc/paper_files/paper/2024/hash/df29d63af05cb91d705cf06ba5945b9d-Abstract-Conference.html (PeTTA abstract) ; baseline list at main.tex l.595-609
* ref-sar2023-table (l. 125 of the pre-audit file): Same error in Table I: the row citing EATA, CoTTA, SAR and RoTTA ends 'i.i.d. batches'.
  Source: as for ref-sar2023
* ref-l2sp2018 (l. 140-141 of the pre-audit file): The subject of 'anchors fine-tuning to a prior ... or averages a teacher' is 'Test-time adaptation in vision', but L2-SP is transfer learning, EWC continual learning and Mean Teacher semi-supervised learning.
  Source: Titles of the three entries as verified by the first audit (ICML 2018 PMLR 80; PNAS 114(13); NeurIPS 30)
* ref-meanteacher2017 (l. 127 of the pre-audit file): The table row files Mean Teacher under 'prior weights' and 'pull to a prior'; it averages the student's weights and has no prior.
  Source: Title of the entry ('Weight-averaged consistency targets ...'), verified by the first audit
* ref-medbn (l. 607-608 of the pre-audit file): MedBN is not robust aggregation: it replaces the mean by the median in the batch-normalisation statistics. The baseline takes the coordinate-wise median of group gradients, because DeepSIC has no batch normalisation (citadel_rx/receivers/robust.py, docstring).
  Source: https://openaccess.thecvf.com/content/CVPR2024/html/Park_MedBN_Robust_Test-Time_Adaptation_against_Malicious_Test_Samples_CVPR_2024_paper.html (abstract via search: 'median batch normalization (MedBN), leveraging the robustness of the median for statistics estimation within the batch normalization layer') ; /home/user/Citradel-Rx/citadel_rx/receivers/robust.py l.1-9
* ref-behrouz2025titans (l. 146-148 of the pre-audit file): Titans does not keep memory at several rates: it has one long-term memory learned at test time beside attention and fixed persistent weights (the paper itself cites it at l.609 for the single-memory receiver). Its write is driven by a surprise measure with forgetting, so 'do not decide what enters' is also inexact; what is absent is a test that can refuse a write.
  Source: https://arxiv.org/abs/2501.00663 and https://neurips.cc/virtual/2025/poster/119639 (abstract via search: a neural long-term memory that learns to memorise at test time, surprise measured by the gradient of an associative-memory loss, forgetting, attention as short-term memory, persistent memory as data-independent parameters)
* ref-behrouz2025titans-table (l. 128 of the pre-audit file): Same point in Table I: 'multi-rate' holds for nested learning, not for Titans.
  Source: as for ref-behrouz2025titans
* ref-athalye2018obfuscated (l. 266 of the pre-audit file): The soft-gate attack is labelled 'as in BPDA'. BPDA keeps the exact function on the forward pass and substitutes a differentiable approximation on the backward pass only. Here the smooth surrogate is the objective itself (pilot_poisoning.py, _soft_objective returns nll * p_acc with p_acc from _soft_gamma); the hard gates are never evaluated inside the attack.
  Source: https://proceedings.mlr.press/v80/athalye18a.html and https://arxiv.org/abs/1802.00420 (via search: the forward computation runs as usual and the backward pass uses a differentiable approximation) ; /home/user/Citradel-Rx/citadel_rx/attacks/pilot_poisoning.py l.489-495
* ref-ilyas2018 (l. 299 of the pre-audit file): The table says the query attacker searches 'with natural-evolution strategies'. The code sends one random probe per attacked block and moves the mean direction once per block by the NACK fraction of that probe against a running baseline (pilot_poisoning.py l.172-182 and l.363-372): no population, no antithetic pairs, no fitness shaping. A reader would take the cell for the query-efficient attack of Ilyas et al.
  Source: /home/user/Citradel-Rx/citadel_rx/attacks/pilot_poisoning.py l.172-182, l.363-372 ; https://proceedings.mlr.press/v80/ilyas18a.html and https://jmlr.org/papers/v15/wierstra14a.html (records verified by the first audit; population-based gradient estimates are the method of both)
* ref-ts38212 (l. 1209 of the pre-audit file): The stated simplification is incomplete: NR attaches a CRC-16 (up to 3824 bits) or CRC-24A to the transport block and, when it segments it, a CRC-24B, not a CRC-24A, to every code block.
  Source: Sionna 2.2.0, sionna/phy/nr/tb_encoder.py l.238-250 (CRC16 or CRC24A on the transport block, CRC24B per code block) ; https://www.3gpp.org/ftp/tsg_ran/WG1_Rl1/DRAFT/Draft_versions/draft_38212-j20.docx (search result: title page '3GPP TS 38.212 V19.2.0 (2025-12)', clauses on transport-block CRC attachment and code-block segmentation) ; the 3824-bit threshold from secondary summaries of clause 6.2.1 / 7.2.1
* ref-sionna-version (l. 1197-1198 of the pre-audit file): The sentence cites TR 38.901 V19.5.0 for the drops, but Sionna 2.2.0 generates them from its V19.2 parameter tables (sionna/phy/channel/tr38901/umi.py: spec_version default '19.2'; scripts/make_umi_channels.py l.56 and l.78 do not set it).
  Source: Installed package sionna-no-rt 2.2.0, sionna/phy/channel/tr38901/umi.py l.61 and l.154 ; /home/user/Citradel-Rx/scripts/make_umi_channels.py l.56-57, l.78-79
* ref-kunsch1989 (l. 638 of the pre-audit file): The implemented bootstrap wraps the resampled runs around the end of the series (scripts/revision_stats.py l.100-111, index modulo n). Kunsch's moving-block bootstrap does not wrap; the sentence should say what was computed.
  Source: /home/user/Citradel-Rx/scripts/revision_stats.py l.100-113 ; https://projecteuclid.org/journals/annals-of-statistics/volume-17/issue-3/The-Jackknife-and-the-Bootstrap-for-General-Stationary-Observations/10.1214/aos/1176347265.full (record verified by the first audit)
* prior-3 (l. 56-58 of the pre-audit file): The abstract states the principle as a sufficient condition ('Such a receiver resists pilot poisoning if ...'). The paper's own results contradict sufficiency: Citadel-Rx meets the condition and is not protected at 16-QAM, in the coded 3GPP scene, under A4 and during a legitimate channel change (Discussion, 'Where it fails'). The rest of the abstract already reports where the receiver resists and where it fails, so the principle only needs to be stated as what the paper argues.
  Source: main.tex l.59-70 (abstract), l.1300-1329 (Discussion)
* prior-4 (l. 98-100 of the pre-audit file): The italic statement of the principle is unconditional and nothing near it says that the receiver which satisfies it fails in several of the settings evaluated.
  Source: main.tex l.1300-1329
* prior-5 (l. 1349-1351 of the pre-audit file): The Conclusion opens with the same unconditional claim; the failures come only at the end of the paragraph.
  Source: main.tex l.1349-1369
* prior-12 (l. 176 of the pre-audit file): The heading of contribution 4, 'An evaluation built to be hard to pass', is the paper's judgement of itself; state what the evaluation contains.
  Source: main.tex l.176-194
* prior-8 (l. 605-606 of the pre-audit file): The drift-detection baseline is built after Uzlaner et al. (citadel_rx/receivers/drift.py, docstring: 'after Uzlaner, Raviv, Shlezinger, Todros'; the statistic is a simpler stand-in), and the paper does not cite that work.
  Source: https://arxiv.org/abs/2407.09134 (search result: N. Uzlaner, T. Raviv, N. Shlezinger, K. Todros, submitted 12 Jul 2024; drift detection to decide when a deep receiver is re-trained, and a modular variant that decides which sub-module) ; https://cris.iucc.ac.il/en/publications/asynchronous-online-adaptation-via-modular-drift-detection-for-de/ (IEEE Trans. Wireless Commun., 'accepted/in press', no volume or pages)
* prior-8b (l. 139 of the pre-audit file): The related work omits the two closest receiver-side works on when an update is applied and on what is carried between blocks: modular drift detection and online Bayesian learning of modular deep receivers. Both address channel variation, not an adversary, which is the distinction the paper draws.
  Source: https://arxiv.org/abs/2407.09134 (as above) ; https://arxiv.org/abs/2511.06045 (search result: Y. Gusakov, O. Simeone, T. Routtenberg, N. Shlezinger, submitted 8 Nov 2025; online training as Bayesian tracking of the network parameters, single-step adaptation in place of multi-epoch gradient descent, one localised Bayesian update per module)
* prior-9 (l. 149-151 of the pre-audit file): 'Adversarial examples against deep physical-layer models' is supported only by a paper on modulation classifiers. Missing: the over-the-air attack on a learned end-to-end link by the same authors, which compares the attack with jamming, and the over-the-air poisoning of a wireless learner that re-trains on sensed data, which predates Wu et al.
  Source: https://arxiv.org/abs/1902.08391 and https://peeref.com/works/18396597 (IEEE Commun. Lett., vol. 23, no. 5, pp. 847-850, May 2019, DOI 10.1109/LCOMM.2019.2901469; abstract: physical black-box attacks on autoencoder links, more destructive than jamming) ; https://dblp.org/rec/journals/tmc/SagduyuSE21.html (IEEE Trans. Mob. Comput. 20(2): 306-319, 2021; DOI 10.1109/TMC.2019.2950398) and https://arxiv.org/abs/1911.00500 (abstract: the adversary transmits in the sensing period to manipulate the transmitter's test inputs and its re-training data)
* prior-10 (l. 139-143 of the pre-audit file): Poisoning of test-time adaptation is represented by one attack paper. Missing: the test-time poisoning attack of Cong et al.; the study of Su et al., which finds the methods more robust once the attacker sees neither the online weights nor other users' samples (relevant to how the white-box, grey-box and query attackers here are read); and the periodic-reset baseline RDumb (relevant to the rollback argument).
  Source: https://dblp.org/rec/conf/sp/CongHSZ24 and https://ieeexplore.ieee.org/document/10646694/ (search result: SP 2024, pp. 1306-1324; arXiv:2308.08505) ; https://proceedings.iclr.cc/paper_files/paper/2025/hash/bb309cc1fbdb88ea755bd7cee4b310ec-Abstract-Conference.html (seven authors; abstract: under realistic assumptions, without the real-time weights and other users' benign samples, TTA methods are more robust than previously believed; arXiv:2410.04682) ; https://neurips.cc/virtual/2023/poster/71448 and https://arxiv.org/abs/2306.05401 (abstract: RDumb periodically resets the model to its pre-trained state and is better than or on par with the state of the art on all benchmarks considered)
* prior-11 (l. 144-146 of the pre-audit file): Poisoning theory is represented by one 2017 reference for convex learners. A 2026 ICML paper gives a theory of continual learning under data poisoning (no defence when a linear proportion of tasks is poisoned without a bound on the noise; defences for infrequent or bounded attacks, one of which compares consecutive updates), the nearest theoretical counterpart of gated consolidation with a bounded step.
  Source: https://proceedings.mlr.press/v306/hu26n.html (search result: Yiting Hu, Lingjie Duan, Proc. 43rd ICML, PMLR 306:44906-44935, 2026) ; https://icml.cc/virtual/2026/poster/65304 (summary: one defence compares consecutive learning updates to detect suspicious tasks) ; https://arxiv.org/abs/2606.29841

### Fields still unconfirmed (read once on the source before submission)

* wu2024 (arXiv:2409.02430): only the abstract and search extracts of the HTML were seen; the PDF was not read. Unconfirmed and still in the paper: that the SER of \cite{shlezinger2021,raviv2023,wu2024} is the fraction of symbol slots with at least one user wrong (l.306). The arXiv title is spelt 'Receviers'; the entry reproduces it (the author may add [sic]).
* shlezinger2021: that the per-user cosine fading with periods 51, 39, 33, 21 is in the DeepSIC paper (Table tab:setup, l.586). The project's notes trace the periods to the reference code released with raviv2024; the DeepSIC paper could not be opened. If the periods are not in the DeepSIC paper, cite \cite{raviv2024} there.
* shlezinger2021: the form of online training in the DeepSIC paper (whether its labels are decoded codewords) rests on short search extracts.
* raviv2023: that f(x)=tanh(0.5x) is the non-linearity of that paper (l.207); the paper does evaluate a synthetic non-linear channel.
* ts38211: 3GPP cover date of V19.2.0 and the clause numbers 5.2.1 and 6.3.1.1 in V19.2.0 (taken from earlier releases and from the Sionna 2.2.0 source).
* ts38212: cover date 2025-12 seen only as the title of a WG1 draft file on 3gpp.org; the 3824-bit threshold of clause 6.2.1 from secondary summaries and the Sionna source.
* raviv2024 (new): volume, issue, pages and DOI from two university repositories; month 'Aug.' inferred from the issue number.
* sadeghi2019ae (new): volume, issue, pages from secondary indexes and the DOI; sagduyu2021 (new): DBLP record, month inferred from the issue number.
* uzlaner2024 and gusakov2025 (new): cited as arXiv preprints; journal versions (IEEE TWC; IEEE TSP) are listed as in press by repositories and were not confirmed.
* hu2026 (new): PMLR volume and pages from a search result on proceedings.mlr.press; cong2024 pages from a search result on dblp.org; rdumb2023 'vol. 36' is the NeurIPS 2023 volume, not seen on the paper's page.
* Every record in this file was confirmed from search results on the authoritative domains, not from opened pages, except pypi.org (fetched). arxiv.org, 3gpp.org, etsi.org, ieeexplore.ieee.org, dblp.org, proceedings.mlr.press, github.com (third-party repositories) and weizmann.ac.il are outside the session's allowed network domains.
* Acknowledgment: it still says the COST2100 traces were released with `raviv2023`; the project's notes trace
  them to the public code released with `raviv2024`. The sentence was left for the author (see ref-raviv2023-ack above).

## Final read (2026-11-11)

* The Acknowledgment and Table `tab:setup` now credit the COST2100 traces to the public code released with
  `raviv2024` (finding ref-raviv2023-ack), in agreement with Table `tab:hyper`; the notes above that say the
  Acknowledgment "still says `raviv2023`" describe the state before this change.
* The reference list is now numbered in order of first citation (59 entries, all cited; entry texts unchanged).
  The declaration of Table `tab:setup` was moved below the paragraph "Receivers." so that the source order of
  the citations is the order in which they appear on the page (same page and position in the PDF).
* The month of `raviv2024` and `sagduyu2021` and the volume of `rdumb2023` remain omitted: not confirmed on a record.
