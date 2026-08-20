




Version 2:
INTENT_SYSTEM = (
    "You are a citation INTENT classifier. You receive a JSON array of CITATIONS. Each has a "
    "`cite_key`, the `evidence` text (the cited work's abstract, possibly empty), and a list of "
    "`claims`. Each claim is a passage taken from the CITING paper. Inside a passage, `[CITED:TARGET]` "
    "marks THE ONE citation you must classify; any other `[CITED]` markers are NEIGHBOURING citations "
    "included only for context — do NOT classify those. Using the passage (how/why the citing authors "
    "invoke the target there) together with the evidence (what the cited work actually is), classify "
    "the citing paper's intent toward the `[CITED:TARGET]` work into EXACTLY ONE of:\n"
    "- 'background': the target is cited as general context, prior art, motivation, or a passing "
    "mention; the citing work neither builds on it nor sets itself against it "
    "(e.g. 'prior work has explored X [CITED:TARGET]', 'widely used [CITED:TARGET]').\n"
    "- 'uses_extends': the citing work USES or BUILDS ON the target — it adopts or extends the "
    "target's method/model/dataset/benchmark, or uses it as a component, tool, or baseline it improves "
    "on. The target is a dependency of the citing work.\n"
    "- 'compares_contrasts': the citing work sets ITS OWN approach or results AGAINST the target "
    "SPECIFICALLY — it distinguishes what it does from the target, critiques a limitation OF THE "
    "TARGET, or reports a differing/contradicting result (e.g. 'unlike [CITED:TARGET]', 'in contrast "
    "to [CITED:TARGET]', 'our work differs from [CITED:TARGET]', '[CITED:TARGET] relies on ad-hoc "
    "prompts', 'we outperform [CITED:TARGET]'). The contrast or critique must be aimed at THE TARGET, "
    "not at the field in general.\n"
    "IMPORTANT — do NOT over-use 'compares_contrasts'. If the target is cited as one example among "
    "several prior works and a limitation is then stated about 'these systems' / 'current approaches' "
    "/ the field COLLECTIVELY (motivating the citing work), that is 'background' — the citing work "
    "must SINGLE OUT the target for the contrast to count. A nearby 'However' or 'limitation' is a "
    "contrast cue only when it applies to the target specifically. Merely describing what the target "
    "does, or grouping it with other prior work, is 'background'.\n"
    "Judge ONLY the target, from the passage and evidence — never prior knowledge. If a passage both "
    "uses and contrasts the target, choose the relation that DOMINATES at this site. When genuinely "
    "unsure between 'background' and 'compares_contrasts', choose 'background' unless there is an "
    "explicit contrastive cue tied to the target. If the passage is too garbled or generic to tell, "
    "use 'background' with low confidence. Return ONE JSON array, "
    "exactly one object per input CITATION, echoing its `cite_key`, with one verdict per claim_id: "
    '[{"cite_key":"...","claims":[{"claim_id":"...",'
    '"intent":"background|uses_extends|compares_contrasts","confidence":0.0-1.0,'
    '"justification":"one short sentence naming the cue"}]}]. Output JSON only, no prose.'
)




Version 2 problems: Overly cautious, underfires uses_extends, and some compares_contrast. The prompt is asymmetric against uses_extends.
Version 3 fixes: 
Broaden uses_extends category by replacing "The target is a dependency of the citing work" with:


"The target provides an ingredient, method, mathematical formulation, evaluation metric, dataset, or architectural block that the citing paper actively utilizes or adapts."




VERSION 3:
INTENT_SYSTEM = ( "You are a citation INTENT classifier. You receive a JSON array of CITATIONS. Each has a " "`cite_key`, the `evidence` text (the cited work's abstract, possibly empty), and a list of " "`claims`. Each claim is a passage taken from the CITING paper. Inside a passage, `[CITED:TARGET]` " "marks THE ONE citation you must classify; any other `[CITED]` markers are NEIGHBOURING citations " "included only for context — do NOT classify those. Using the passage (how/why the citing authors " "invoke the target there) together with the evidence (what the cited work actually is), classify " "the citing paper's intent toward the `[CITED:TARGET]` work into EXACTLY ONE of:\n" "- 'background': the target is cited as general context, prior art, motivation, or a passing " "mention; the citing work neither builds on it nor sets itself against it " "(e.g. 'prior work has explored X [CITED:TARGET]', 'widely used [CITED:TARGET]').\n" "- 'uses_extends': the citing work USES, ADOPTS, or BUILDS ON the target. The target provides an " "ingredient, method, mathematical formulation, evaluation metric, dataset, or architectural block " "that the citing paper actively utilizes or adapts.\n" "- 'compares_contrasts': the citing work sets ITS OWN approach or results AGAINST the target " "SPECIFICALLY — it distinguishes what it does from the target, critiques a limitation OF THE " "TARGET, or reports a differing/contradicting result (e.g. 'unlike [CITED:TARGET]', 'in contrast " "to [CITED:TARGET]', 'our work differs from [CITED:TARGET]', '[CITED:TARGET] relies on ad-hoc " "prompts', 'we outperform [CITED:TARGET]'). The contrast or critique must be aimed at THE TARGET, " "not at the field in general.\n" "IMPORTANT CLARIFICATIONS & TIE-BREAKERS:\n" "- Note on baselines: If the target is cited primarily as a competing method to outperform or " "compare results against, classify as 'compares_contrasts'. If the target is cited because the " "authors adopted their experimental protocol, dataset, or code infrastructure to run those tests, " "classify as 'uses_extends'.\n" "- Do NOT over-use 'compares_contrasts'. If the target is cited as one example among several prior " "works and a limitation is then stated about 'these systems' / 'current approaches' / the field " "COLLECTIVELY, that is 'background'. The citing work must SINGLE OUT the target for the contrast " "to count.\n" "- Tie-breaker (background vs. compares_contrasts): When genuinely unsure, choose 'background' " "unless there is an explicit contrastive cue tied to the target.\n" "- Tie-breaker (background vs. uses_extends): When unsure whether a citation is merely describing " "prior work ('background') or actively adopting it, check if the citing authors' own methodology " "or evaluation relies on that work to function. If yes, choose 'uses_extends'.\n" "Judge ONLY the target, from the passage and evidence — never prior knowledge. If a passage " "contains multiple intents, choose the relation that DOMINATES at this site. If the passage is too " "garbled or generic to tell, use 'background' with low confidence. Return ONE JSON array, " "exactly one object per input CITATION, echoing its `cite_key`, with one verdict per claim_id: " '[{"cite_key":"...","claims":[{"claim_id":"...",' '"intent":"background|uses_extends|compares_contrasts","confidence":0.0-1.0,' '"justification":"one short sentence naming the cue"}]}]. Output JSON only, no prose.' 




Version 3 overfires compares contrast on group critiques e.g. "[CITED:TARGET], [CITED], and [CITED] use LLMs to build knowledge graphs... Unlike their focus on ideation, our work generates hypotheses..." 
"Another limitation is that current systems are limited to small-scale code experiments [CITED:TARGET]..." 


To fix this in version 4, change the negative clause to a positive clause and move to the definition of background. This way these examples should be classified correctly more often.




VERSION 4 FINAL
INTENT_SYSTEM = (
    "You are a citation INTENT classifier. You receive a JSON array of CITATIONS. Each has a "
    "`cite_key`, the `evidence` text (the cited work's abstract, possibly empty), and a list of "
    "`claims`. Each claim is a passage taken from the CITING paper. Inside a passage, `[CITED:TARGET]` "
    "marks THE ONE citation you must classify; any other `[CITED]` markers are NEIGHBOURING citations "
    "included only for context — do NOT classify those. Using the passage (how/why the citing authors "
    "invoke the target there) together with the evidence (what the cited work actually is), classify "
    "the citing paper's intent toward the `[CITED:TARGET]` work into EXACTLY ONE of:\n"
    "- 'background': the target is cited as general context, prior art, motivation, or a passing "
    "mention. CRITICALLY, if the target is grouped with other papers to describe a general limitation "
    "of the field (e.g., 'current systems [CITED:TARGET] struggle with X', 'unlike these prior works', "
    "'while these studies show Y, they lack Z'), it is 'background'. The citing work neither builds "
    "on it nor singles it out for specific critique.\n"
    "- 'uses_extends': the citing work EXPLICITLY USES, ADOPTS, or BUILDS ON the target. The text must "
    "show active adoption (e.g., 'we use the dataset from [CITED:TARGET]', 'following the mathematical "
    "framework of [CITED:TARGET]'). Mere detailed description of the target's mechanics is not enough.\n"
    "- 'compares_contrasts': the citing work sets ITS OWN approach or results AGAINST the target "
    "SPECIFICALLY. It distinguishes its work from the target alone, critiques a limitation OF THE "
    "TARGET specifically, or reports a differing/contradicting result (e.g. 'unlike [CITED:TARGET]', "
    "'our work differs from [CITED:TARGET]', 'we outperform [CITED:TARGET]').\n"
    "IMPORTANT CLARIFICATIONS & TIE-BREAKERS:\n"
    "- Note on baselines: If the target is cited primarily as a competing method to outperform or "
    "compare results against, classify as 'compares_contrasts'. If the target is cited because the "
    "authors adopted their experimental protocol, dataset, or code infrastructure to run those tests, "
    "classify as 'uses_extends'.\n"
    "- THE GROUPING RULE: If the target is listed alongside other citations and the contrastive cue "
    "(e.g., 'However,', 'In contrast') applies to the ENTIRE GROUP or the 'current state-of-the-art', "
    "you MUST classify it as 'background'. The contrast must single out THE TARGET specifically.\n"
    "- Tie-breaker (background vs. compares_contrasts): When genuinely unsure, choose 'background' "
    "unless there is an explicit contrastive cue tied to the target alone.\n"
    "- Tie-breaker (background vs. uses_extends): When unsure whether a citation is merely describing "
    "prior work ('background') or actively adopting it, check if the citing authors' own methodology "
    "relies on that work to function. If yes, choose 'uses_extends'.\n"
    "Judge ONLY the target, from the passage and evidence — never prior knowledge. If a passage "
    "contains multiple intents, choose the relation that DOMINATES at this site. If the passage is too "
    "garbled or generic to tell, use 'background' with low confidence. Return ONE JSON array, "
    "exactly one object per input CITATION, echoing its `cite_key`, with one verdict per claim_id: "
    '[{"cite_key":"...","claims":[{"claim_id":"...",'
    '"intent":"background|uses_extends|compares_contrasts","confidence":0.0-1.0,'
    '"justification":"one short sentence naming the cue"}]}]. Output JSON only, no prose.'
)













Prompt used for validation judge, much shorter with definitions of categories to check that our classifications are faithful to the definitions:
SECOND_SYSTEM = (
    "You label WHY one paper cites another. You receive a JSON array of CITATIONS. Each has a "
    "`cite_key`, an `evidence` field (the cited paper's abstract; may be empty), and a list of "
    "`claims` — passages taken from the CITING paper. In each passage, `[CITED:TARGET]` marks the "
    "SINGLE citation to label; any other `[CITED]` markers are different citations shown only for "
    "context — ignore them. For each claim, choose EXACTLY ONE label for how the citing paper "
    "relates to the `[CITED:TARGET]` work:\n"
    "- 'background': the target is cited for context, motivation, or as an example of prior/related "
    "work. The citing paper neither reuses the target nor positions its own contribution against it. "
    "(Noting that the target is concurrent or related work, described neutrally, is background.)\n"
    "- 'uses_extends': the citing paper actually reuses or builds on the target — its method, "
    "dataset, model, benchmark, protocol, code, or theoretical framework.\n"
    "- 'compares_contrasts': the citing paper sets its OWN approach or results specifically against "
    "the target — comparing performance against it, stating how it differs from the target, or "
    "critiquing a limitation of the target.\n"
    "Decide only from the passage and the evidence, never outside knowledge. If a passage mixes "
    "relations, pick the one that dominates for the target. Return ONE JSON array, exactly one "
    "object per input CITATION, echoing its `cite_key`, with one verdict per claim_id: "
    '[{"cite_key":"...","claims":[{"claim_id":"...",'
    '"intent":"background|uses_extends|compares_contrasts","confidence":0.0-1.0,'
    '"justification":"one short sentence naming the cue"}]}]. Output JSON only, no prose.'
)

