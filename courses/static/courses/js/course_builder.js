/* ============================================================
   NeoLearn Course Builder
   Shared Admin / Teacher Course Builder JavaScript
   ============================================================

   This file contains the JavaScript previously embedded inside
   the Course Builder HTML.

   Backend operations remain normal Django GET/POST requests.
   No fetch/AJAX logic is introduced here.
   ============================================================ */


(function () {
        const modal = document.getElementById("quizModal");
        const form = document.getElementById("quizForm");
        const body = document.getElementById("quizCreateBody");
        const container = document.getElementById("quizQuestionsContainer");
        const addButton = document.getElementById("addQuizQuestionBtn");
        const marksInput = document.getElementById("quizMarksPerQuestion");
        const countLabel = document.getElementById("quizQuestionCount");
        const totalQuestionsLabel = document.getElementById("quizTotalQuestionsPreview");
        const totalMarksPerQuestionLabel = document.getElementById("quizTotalMarksPerQuestionPreview");
        const totalMarksLabel = document.getElementById("quizTotalMarksPreview");

        if (!modal || !form || !container || !addButton) {
            return;
        }

        function getBlocks() {
            return Array.from(
                container.querySelectorAll(".quiz-question-block")
            );
        }

        function updateQuestionNumbers() {
            const blocks = getBlocks();

            blocks.forEach(function (block, index) {
                const number = index + 1;

                block.dataset.questionNumber = number;

                const badge = block.querySelector(".question-number-badge");
                if (badge) {
                    badge.textContent = number;
                }

                const title = block.querySelector(".question-title");
                if (title) {
                    title.textContent = "Question " + number;
                }

                const questionInput = block.querySelector("[name^=\"question_text_\"]");
                const optionA = block.querySelector("[name^=\"option_a_\"]");
                const optionB = block.querySelector("[name^=\"option_b_\"]");
                const optionC = block.querySelector("[name^=\"option_c_\"]");
                const optionD = block.querySelector("[name^=\"option_d_\"]");

                if (questionInput) questionInput.name = "question_text_" + number;
                if (optionA) optionA.name = "option_a_" + number;
                if (optionB) optionB.name = "option_b_" + number;
                if (optionC) optionC.name = "option_c_" + number;
                if (optionD) optionD.name = "option_d_" + number;

                block.querySelectorAll("input[type=\"radio\"]").forEach(function (radio) {
                    radio.name = "correct_answer_" + number;
                });

                const removeButton = block.querySelector(".quiz-remove-question");
                if (removeButton) {
                    const isOnlyQuestion = blocks.length === 1;
                    removeButton.disabled = isOnlyQuestion;
                    removeButton.title = isOnlyQuestion
                        ? "At least one question is required"
                        : "Remove Question " + number;
                }
            });

            const count = blocks.length;

            if (countLabel) {
                countLabel.textContent = count + (count === 1 ? " question" : " questions");
            }

            if (totalQuestionsLabel) {
                totalQuestionsLabel.textContent = count;
            }

            updateTotalPreview();
        }

        function updateTotalPreview() {
            const count = getBlocks().length;
            const marks = Number.parseInt(
                marksInput ? marksInput.value : "0",
                10
            );
            const safeMarks = Number.isFinite(marks) && marks > 0 ? marks : 0;

            if (totalMarksPerQuestionLabel) {
                totalMarksPerQuestionLabel.textContent = safeMarks;
            }

            if (totalMarksLabel) {
                totalMarksLabel.textContent = count * safeMarks;
            }
        }

        function createQuestionBlock(number) {
            const block = document.createElement("div");

            block.className = "quiz-question-block overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm";
            block.dataset.questionNumber = number;

            block.innerHTML = `
                <div class="flex items-center justify-between gap-3 border-b border-slate-100 bg-slate-50/70 px-4 py-3">
                    <div class="flex min-w-0 items-center gap-3">
                        <span class="question-number-badge flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-violet-600 text-xs font-black text-white">${number}</span>
                        <div class="min-w-0">
                            <p class="question-title text-sm font-black text-slate-900">Question ${number}</p>
                            <p class="text-[10px] font-medium text-slate-400">Four options · one correct answer</p>
                        </div>
                    </div>

                    <button
                        type="button"
                        class="quiz-remove-question inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-red-200 px-2.5 py-2 text-[11px] font-bold text-red-600 transition hover:bg-red-50"
                        title="Remove this question">
                        <i class="ri-delete-bin-6-line"></i>
                        <span class="hidden sm:inline">Remove</span>
                    </button>
                </div>

                <div class="space-y-4 p-4">
                    <div>
                        <label class="neo-label">
                            Question
                            <span class="text-red-500">*</span>
                        </label>
                        <textarea
                            name="question_text_${number}"
                            rows="3"
                            class="neo-input resize-none"
                            placeholder="Enter the question"></textarea>
                    </div>

                    <div class="grid grid-cols-1 gap-3 md:grid-cols-2">
                        <div>
                            <label class="neo-label">Option A <span class="text-red-500">*</span></label>
                            <input type="text" name="option_a_${number}" class="neo-input" placeholder="Enter Option A">
                        </div>
                        <div>
                            <label class="neo-label">Option B <span class="text-red-500">*</span></label>
                            <input type="text" name="option_b_${number}" class="neo-input" placeholder="Enter Option B">
                        </div>
                        <div>
                            <label class="neo-label">Option C <span class="text-red-500">*</span></label>
                            <input type="text" name="option_c_${number}" class="neo-input" placeholder="Enter Option C">
                        </div>
                        <div>
                            <label class="neo-label">Option D <span class="text-red-500">*</span></label>
                            <input type="text" name="option_d_${number}" class="neo-input" placeholder="Enter Option D">
                        </div>
                    </div>

                    <div class="rounded-xl border border-slate-200 bg-slate-50 p-3">
                        <p class="mb-2 text-xs font-black text-slate-800">
                            Correct Answer <span class="text-red-500">*</span>
                        </p>
                        <div class="grid grid-cols-2 gap-2 sm:grid-cols-4">
                            <label class="flex cursor-pointer items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-xs font-bold text-slate-700 transition hover:border-violet-300 hover:bg-violet-50/40">
                                <input type="radio" name="correct_answer_${number}" value="A" class="h-4 w-4 accent-violet-600">
                                <span>Option A</span>
                            </label>
                            <label class="flex cursor-pointer items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-xs font-bold text-slate-700 transition hover:border-violet-300 hover:bg-violet-50/40">
                                <input type="radio" name="correct_answer_${number}" value="B" class="h-4 w-4 accent-violet-600">
                                <span>Option B</span>
                            </label>
                            <label class="flex cursor-pointer items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-xs font-bold text-slate-700 transition hover:border-violet-300 hover:bg-violet-50/40">
                                <input type="radio" name="correct_answer_${number}" value="C" class="h-4 w-4 accent-violet-600">
                                <span>Option C</span>
                            </label>
                            <label class="flex cursor-pointer items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-xs font-bold text-slate-700 transition hover:border-violet-300 hover:bg-violet-50/40">
                                <input type="radio" name="correct_answer_${number}" value="D" class="h-4 w-4 accent-violet-600">
                                <span>Option D</span>
                            </label>
                        </div>
                    </div>
                </div>
            `;

            return block;
        }

        addButton.addEventListener("click", function () {
            const blocks = getBlocks();
            const nextNumber = blocks.length + 1;
            const newBlock = createQuestionBlock(nextNumber);

            container.appendChild(newBlock);
            updateQuestionNumbers();

            window.requestAnimationFrame(function () {
                newBlock.scrollIntoView({
                    behavior: "auto",
                    block: "start"
                });
            });
        });

        container.addEventListener("click", function (event) {
            const button = event.target.closest(".quiz-remove-question");

            if (!button || button.disabled) {
                return;
            }

            const blocks = getBlocks();

            if (blocks.length <= 1) {
                return;
            }

            const block = button.closest(".quiz-question-block");

            if (block) {
                block.remove();
                updateQuestionNumbers();
            }
        });

        if (marksInput) {
            marksInput.addEventListener("input", updateTotalPreview);
            marksInput.addEventListener("change", updateTotalPreview);
        }

        form.addEventListener("reset", function () {
            window.setTimeout(updateQuestionNumbers, 0);
        });

        updateQuestionNumbers();

        /*
         * Start every fresh opening at the top of the form body.
         * This fixes the previous nested-scroll / remembered-scroll UX.
         */
        window.addEventListener("quizModalOpened", function () {
            if (body) {
                body.scrollTop = 0;
            }
        });
    })();


document.addEventListener("DOMContentLoaded", function () {


    const builderConfig =
        document.getElementById("courseBuilderConfig") ||
        document.createElement("div");


    /* =======================================================
       VIDEO SELECTOR
       UI-only selection. Files remain served from Cloudinary
       through the model's CloudinaryField URL.
    ======================================================= */

    const videoSelectors =
        document.querySelectorAll("[data-video-selector]");

    const mainVideoPlayer =
        document.getElementById("mainVideoPlayer");

    const mainVideoSource =
        document.getElementById("mainVideoSource");

    const videoInfoTitle =
        document.getElementById("videoInfoTitle");

    const videoInfoChapter =
        document.getElementById("videoInfoChapter");

    const videoInfoName =
        document.getElementById("videoInfoName");

    const videoInfoDescription =
        document.getElementById("videoInfoDescription");

    const videoInfoCreatedBy =
        document.getElementById("videoInfoCreatedBy");

    const videoInfoUpdatedBy =
        document.getElementById("videoInfoUpdatedBy");

    const videoInfoCreatedAt =
        document.getElementById("videoInfoCreatedAt");

    const videoInfoUpdatedAt =
        document.getElementById("videoInfoUpdatedAt");

    const videoInfoStatus =
        document.getElementById("videoInfoStatus");

    function updateVideoEditButton(card) {

        const editButton =
            document.querySelector(
                ".video-main-grid .js-edit-video"
            );

        if (!editButton || !card) {
            return;
        }

        const editId =
            card.dataset.editId || "";

        editButton.dataset.id = editId;

        editButton.dataset.name =
            card.dataset.editName || "";

        editButton.dataset.description =
            card.dataset.editDescription || "";

        editButton.dataset.status =
            card.dataset.editStatus || "draft";

        editButton.dataset.order =
            card.dataset.editOrder || "";

        /*
         * The Video Information card has one Edit button, but the
         * selected video can change. Always point the button to the
         * modal belonging to the selected video.
         */
        editButton.dataset.openModal =
            "videoEditModal-" + editId;

    }


    function updateSelectedVideo(card) {

        if (!card) {
            return;
        }

        videoSelectors.forEach(function (item) {

            item.classList.remove("active");

        });

        card.classList.add("active");


        if (mainVideoSource && mainVideoPlayer) {

            mainVideoSource.src =
                card.dataset.videoUrl || "";

            mainVideoPlayer.load();

        }


        if (videoInfoTitle) {

            videoInfoTitle.textContent =
                card.dataset.videoName || "Untitled Video";

        }


        if (videoInfoName) {

            videoInfoName.textContent =
                card.dataset.videoName || "Untitled Video";

        }


        if (videoInfoDescription) {

            videoInfoDescription.textContent =
                card.dataset.videoDescription || "No description available.";

        }


        if (videoInfoCreatedBy) {

            videoInfoCreatedBy.textContent =
                card.dataset.videoCreatedBy || "System";

        }


        if (videoInfoUpdatedBy) {

            videoInfoUpdatedBy.textContent =
                card.dataset.videoUpdatedBy || "System";

        }


        if (videoInfoCreatedAt) {

            videoInfoCreatedAt.textContent =
                card.dataset.videoCreatedAt || "—";

        }


        if (videoInfoUpdatedAt) {

            videoInfoUpdatedAt.textContent =
                card.dataset.videoUpdatedAt || "—";

        }


        if (videoInfoStatus) {

            videoInfoStatus.textContent =
                card.dataset.videoStatusDisplay || "Draft";

            videoInfoStatus.classList.remove(
                "status-published",
                "status-draft"
            );

            if (
                card.dataset.videoStatus ===
                "published"
            ) {

                videoInfoStatus.classList.add(
                    "status-published"
                );

            } else {

                videoInfoStatus.classList.add(
                    "status-draft"
                );

            }

        }


        updateVideoEditButton(card);

    }


    videoSelectors.forEach(function (card) {

        card.addEventListener(
            "click",
            function (event) {

                if (
                    event.target.closest(
                        ".content-menu-button, .menu"
                    )
                ) {
                    return;
                }

                updateSelectedVideo(card);

            }
        );


        card.addEventListener(
            "keydown",
            function (event) {

                if (
                    event.key === "Enter" ||
                    event.key === " "
                ) {

                    event.preventDefault();

                    updateSelectedVideo(card);

                }

            }
        );

    });


    if (videoSelectors.length) {

        updateSelectedVideo(
            videoSelectors[0]
        );

    }



    /* =======================================================
       PDF SELECTOR
       Selecting the second/third/etc. PDF changes the main
       preview and information card without a page reload.
       Backend data and PDF URLs remain unchanged.
    ======================================================= */

    const pdfSelectors =
        document.querySelectorAll("[data-pdf-selector]");

    const pdfMainThumbnail =
        document.getElementById("pdfMainThumbnail");

    const pdfMainOrderBadge =
        document.getElementById("pdfMainOrderBadge");

    const pdfInfoTitle =
        document.getElementById("pdfInfoTitle");

    const pdfInfoChapter =
        document.getElementById("pdfInfoChapter");

    const pdfInfoDescription =
        document.getElementById("pdfInfoDescription");

    const pdfInfoFile =
        document.getElementById("pdfInfoFile");

    const pdfInfoFileName =
        document.getElementById("pdfInfoFileName");

    const pdfInfoThumbnail =
        document.getElementById("pdfInfoThumbnail");

    const pdfInfoOrder =
        document.getElementById("pdfInfoOrder");

    const pdfInfoCreatedBy =
        document.getElementById("pdfInfoCreatedBy");

    const pdfInfoCreatedAt =
        document.getElementById("pdfInfoCreatedAt");

    const pdfInfoUpdatedBy =
        document.getElementById("pdfInfoUpdatedBy");

    const pdfInfoUpdatedAt =
        document.getElementById("pdfInfoUpdatedAt");

    const pdfInfoStatus =
        document.getElementById("pdfInfoStatus");

    const pdfMainEditButton =
        document.getElementById("pdfMainEditButton");

    const pdfMainThumbnailButton =
        document.getElementById("pdfMainThumbnailButton");


    function updateSelectedPdf(card) {

        if (!card) {
            return;
        }


        pdfSelectors.forEach(function (item) {

            item.classList.remove("active");

            const selectedBadge =
                item.querySelector(
                    ".pdf-selected-badge"
                );

            if (selectedBadge) {
                selectedBadge.remove();
            }

        });


        card.classList.add("active");


        if (!card.querySelector(".pdf-selected-badge")) {

            const badge =
                document.createElement("span");

            badge.className =
                "pdf-selected-badge absolute right-2 top-2 z-10 flex h-6 w-6 items-center justify-center rounded-full bg-blue-600 text-white shadow-sm";

            badge.innerHTML =
                '<i class="ri-check-line text-xs font-black"></i>';

            card.appendChild(badge);

        }


        const pdfId =
            card.dataset.pdfId || "";

        const pdfUrl =
            card.dataset.pdfUrl || "";

        const pdfName =
            card.dataset.pdfName || "Untitled PDF";

        const pdfDescription =
            card.dataset.pdfDescription ||
            "No description provided.";

        const pdfStatus =
            card.dataset.pdfStatus || "draft";

        const pdfStatusDisplay =
            card.dataset.pdfStatusDisplay || "Draft";

        const pdfOrder =
            card.dataset.pdfOrder || "—";

        const pdfThumbnail =
            card.dataset.pdfThumbnail || "";

        const pdfCreatedBy =
            card.dataset.pdfCreatedBy || "System";

        const pdfCreatedAt =
            card.dataset.pdfCreatedAt || "—";

        const pdfUpdatedBy =
            card.dataset.pdfUpdatedBy || "System";

        const pdfUpdatedAt =
            card.dataset.pdfUpdatedAt || "—";


        if (pdfMainThumbnail) {

            pdfMainThumbnail.src =
                pdfThumbnail;

            pdfMainThumbnail.alt =
                pdfName;

        }


        if (pdfMainOrderBadge) {

            pdfMainOrderBadge.textContent =
                "PDF " + pdfOrder;

        }


        if (pdfInfoTitle) {

            pdfInfoTitle.textContent =
                pdfName;

        }


        if (pdfInfoChapter) {

            const selectedChapterLabel =
                document.getElementById("courseBuilderSelectedChapterLabel");

            pdfInfoChapter.textContent =
                selectedChapterLabel
                    ? selectedChapterLabel.textContent.trim()
                    : "";

        }


        if (pdfInfoDescription) {

            pdfInfoDescription.textContent =
                pdfDescription;

        }


        if (pdfInfoFile) {

            pdfInfoFile.href =
                pdfUrl;

        }


        if (pdfInfoFileName) {

            pdfInfoFileName.textContent =
                pdfName;

        }


        if (pdfInfoThumbnail) {

            pdfInfoThumbnail.src =
                pdfThumbnail;

            pdfInfoThumbnail.alt =
                pdfName;

        }


        if (pdfInfoOrder) {

            pdfInfoOrder.textContent =
                pdfOrder +
                " (Automatically assigned)";

        }


        if (pdfInfoCreatedBy) {

            pdfInfoCreatedBy.textContent =
                pdfCreatedBy;

        }


        if (pdfInfoCreatedAt) {

            pdfInfoCreatedAt.textContent =
                pdfCreatedAt;

        }


        if (pdfInfoUpdatedBy) {

            pdfInfoUpdatedBy.textContent =
                pdfUpdatedBy;

        }


        if (pdfInfoUpdatedAt) {

            pdfInfoUpdatedAt.textContent =
                pdfUpdatedAt;

        }


        if (pdfInfoStatus) {

            pdfInfoStatus.textContent =
                pdfStatusDisplay;

            pdfInfoStatus.classList.remove(
                "status-published",
                "status-draft"
            );

            if (pdfStatus === "published") {

                pdfInfoStatus.classList.add(
                    "status-published"
                );

            } else {

                pdfInfoStatus.classList.add(
                    "status-draft"
                );

            }

        }


        if (pdfMainEditButton) {

            pdfMainEditButton.dataset.openModal =
                "pdfEditModal-" + pdfId;

        }


        if (pdfMainThumbnailButton) {

            pdfMainThumbnailButton.dataset.openModal =
                "pdfEditModal-" + pdfId;

        }

    }


    pdfSelectors.forEach(function (card) {

        card.addEventListener(
            "click",
            function (event) {

                if (
                    event.target.closest(
                        ".content-menu-button, .menu"
                    )
                ) {
                    return;
                }

                updateSelectedPdf(card);

            }
        );


        card.addEventListener(
            "keydown",
            function (event) {

                if (
                    event.key === "Enter" ||
                    event.key === " "
                ) {

                    event.preventDefault();

                    updateSelectedPdf(card);

                }

            }
        );

    });


    if (pdfSelectors.length) {

        updateSelectedPdf(
            pdfSelectors[0]
        );

    }



    /* =======================================================
       QUIZ EDIT
       One normal POST handles:
       - Quiz settings
       - Existing question edits
       - Existing question deletion
       - New questions
       - Correct answers / options
       No AJAX is used.
    ======================================================= */

    document.querySelectorAll(".quiz-edit-modal-panel").forEach(function (modalPanel) {

        const quizId = modalPanel.querySelector(".quiz-edit-add-question")?.dataset.quizId;

        if (!quizId) {
            return;
        }

        const container =
            document.getElementById("quizEditQuestions-" + quizId);

        const addButton =
            modalPanel.querySelector(".quiz-edit-add-question");

        const marksInput =
            modalPanel.querySelector(".quiz-edit-marks-input");

        const countBadge =
            document.getElementById("quizEditQuestionCountBadge-" + quizId);

        const countPreview =
            document.getElementById("quizEditQuestionCountPreview-" + quizId);

        const marksPreview =
            document.getElementById("quizEditMarksPreview-" + quizId);

        const totalPreview =
            document.getElementById("quizEditTotalPreview-" + quizId);

        const totalText =
            document.getElementById("quizEditTotal-" + quizId);

        const countText =
            document.getElementById("quizEditCountText-" + quizId);

        if (!container || !addButton) {
            return;
        }

        let nextNewIndex = 1;

        container
            .querySelectorAll("[data-new-question='true']")
            .forEach(function (block) {

                const index =
                    Number.parseInt(
                        block.dataset.newIndex || "0",
                        10
                    );

                if (
                    Number.isFinite(index) &&
                    index >= nextNewIndex
                ) {
                    nextNewIndex = index + 1;
                }

            });


        function getQuestionCards() {

            return Array.from(
                container.querySelectorAll(".quiz-edit-question-card")
            );

        }


        function getActiveQuestionCards() {

            return getQuestionCards().filter(function (card) {

                return card.dataset.active !== "false";

            });

        }


        function updateDeleteState(card) {

            const checkbox =
                card.querySelector(".edit-question-delete");

            if (!checkbox) {
                return;
            }

            const activeCount =
                getActiveQuestionCards().length;

            if (
                checkbox.checked &&
                activeCount < 1
            ) {
                checkbox.checked = false;
                card.dataset.active = "true";
            }

            const canDelete =
                activeCount > 1 || checkbox.checked;

            checkbox.disabled = !canDelete;

            card.classList.toggle(
                "is-marked-delete",
                checkbox.checked
            );

            const fields =
                card.querySelectorAll(
                    "input:not(.edit-question-delete), textarea, select"
                );

            fields.forEach(function (field) {

                if (field.type === "radio") {
                    field.disabled = checkbox.checked;
                } else {
                    field.disabled = checkbox.checked;
                }

            });

            const label =
                checkbox.closest("label");

            if (label) {

                label.classList.toggle(
                    "cursor-not-allowed",
                    checkbox.disabled
                );

                label.classList.toggle(
                    "opacity-50",
                    checkbox.disabled
                );

            }

        }


        function updateQuestionNumbers() {

            const cards =
                getQuestionCards();

            let number = 0;

            cards.forEach(function (card) {

                if (card.dataset.active === "false") {
                    return;
                }

                number += 1;

                const numberBadge =
                    card.querySelector(".edit-question-number");

                if (numberBadge) {
                    numberBadge.textContent = number;
                }

                const title =
                    card.querySelector(".edit-question-title");

                if (title) {

                    if (
                        card.dataset.newQuestion === "true"
                    ) {
                        title.textContent =
                            "Question " + number + " · New";
                    } else {
                        title.textContent =
                            "Question " + number;
                    }

                }

            });


            if (countBadge) {
                countBadge.textContent = number;
            }

            if (countPreview) {
                countPreview.textContent = number;
            }

            updateTotal(number);

        }


        function updateTotal(questionCount) {

            const marks =
                Number.parseInt(
                    marksInput ? marksInput.value : "0",
                    10
                );

            const safeMarks =
                Number.isFinite(marks) && marks > 0
                    ? marks
                    : 0;

            const total =
                questionCount * safeMarks;

            if (marksPreview) {
                marksPreview.textContent = safeMarks;
            }

            if (totalPreview) {
                totalPreview.textContent = total;
            }

            if (totalText) {
                totalText.textContent =
                    total + " marks";
            }

            if (countText) {

                countText.textContent =
                    questionCount +
                    (
                        questionCount === 1
                            ? " question"
                            : " questions"
                    ) +
                    " × " +
                    safeMarks +
                    (
                        safeMarks === 1
                            ? " mark"
                            : " marks"
                    );

            }

        }


        function updateAnswerVisualState(card) {

            if (!card) {
                return;
            }

            const options =
                card.querySelectorAll(".quiz-answer-option");

            if (!options.length) {
                return;
            }

            const checked =
                card.querySelector(
                    'input[type="radio"][name^="correct_answer_"]:checked'
                );

            const selectedValue =
                checked
                    ? String(checked.value || "").toUpperCase()
                    : "";

            options.forEach(function (option) {

                const label =
                    String(
                        option.dataset.answerLabel || ""
                    ).toUpperCase();

                const isCorrect =
                    Boolean(
                        selectedValue &&
                        label === selectedValue
                    );

                const isWrong =
                    Boolean(
                        selectedValue &&
                        label !== selectedValue
                    );

                option.classList.toggle(
                    "is-correct",
                    isCorrect
                );

                option.classList.toggle(
                    "is-wrong",
                    isWrong
                );

                const correctBadge =
                    option.querySelector(
                        ".quiz-answer-state.correct"
                    );

                const wrongBadge =
                    option.querySelector(
                        ".quiz-answer-state.wrong"
                    );

                if (correctBadge) {
                    correctBadge.style.display =
                        isCorrect ? "inline-flex" : "none";
                }

                if (wrongBadge) {
                    wrongBadge.style.display =
                        isWrong ? "inline-flex" : "none";
                }

            });

        }


        function attachAnswerVisualHandler(card) {

            if (!card) {
                return;
            }

            card.querySelectorAll(
                '.quiz-answer-option input[type="radio"]'
            ).forEach(function (radio) {

                if (
                    radio.dataset.answerVisualBound === "true"
                ) {
                    return;
                }

                radio.dataset.answerVisualBound = "true";

                radio.addEventListener(
                    "change",
                    function () {
                        updateAnswerVisualState(card);
                    }
                );

            });

            updateAnswerVisualState(card);

        }


        function attachDeleteHandler(card) {

            const checkbox =
                card.querySelector(".edit-question-delete");

            if (!checkbox || checkbox.dataset.bound === "true") {
                return;
            }

            checkbox.dataset.bound = "true";

            checkbox.addEventListener(
                "change",
                function () {

                    if (checkbox.checked) {

                        const activeBefore =
                            getActiveQuestionCards().length;

                        if (activeBefore <= 1) {
                            checkbox.checked = false;
                            return;
                        }

                        card.dataset.active = "false";

                    } else {

                        card.dataset.active = "true";

                    }

                    updateQuestionNumbers();

                    getQuestionCards().forEach(
                        updateDeleteState
                    );

                }
            );

        }


        function attachNewQuestionRemoveHandler(card) {

            const removeButton =
                card.querySelector(
                    ".quiz-edit-remove-new-question"
                );

            if (
                !removeButton ||
                removeButton.dataset.bound === "true"
            ) {
                return;
            }

            removeButton.dataset.bound = "true";

            removeButton.addEventListener(
                "click",
                function () {

                    const activeCount =
                        getActiveQuestionCards().length;

                    if (activeCount <= 1) {
                        return;
                    }

                    card.remove();

                    updateQuestionNumbers();

                    getQuestionCards().forEach(
                        updateDeleteState
                    );

                }
            );

        }


        function createNewQuestionBlock(index) {

            const block =
                document.createElement("div");

            block.className =
                "quiz-edit-question-card quiz-edit-new-question " +
                "overflow-hidden rounded-2xl border border-emerald-200 " +
                "bg-white shadow-sm";

            block.dataset.newQuestion = "true";
            block.dataset.newIndex = index;
            block.dataset.active = "true";

            block.innerHTML = `
                <input
                    type="hidden"
                    name="new_question_index"
                    value="${index}">

                <div class="flex items-center justify-between gap-3 border-b border-emerald-100 bg-emerald-50/60 px-4 py-3">

                    <div class="flex min-w-0 items-center gap-3">

                        <span class="edit-question-number flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-emerald-600 text-xs font-black text-white">
                            New
                        </span>

                        <div class="min-w-0">

                            <p class="edit-question-title text-sm font-black text-slate-900">
                                New Question
                            </p>

                            <p class="text-[10px] font-medium text-slate-400">
                                This question will be added when you save the quiz.
                            </p>

                        </div>

                    </div>

                    <button
                        type="button"
                        class="quiz-edit-remove-new-question inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-red-200 bg-white px-2.5 py-2 text-[11px] font-bold text-red-600 transition hover:bg-red-50">

                        <i class="ri-delete-bin-6-line"></i>

                        <span class="hidden sm:inline">
                            Remove
                        </span>

                    </button>

                </div>

                <div class="space-y-4 p-4">

                    <div>

                        <label class="neo-label">
                            Question
                            <span class="text-red-500">*</span>
                        </label>

                        <textarea
                            name="question_text_new_${index}"
                            rows="3"
                            maxlength="1000"
                            class="neo-input resize-none"
                            placeholder="Enter the question"></textarea>

                    </div>

                    <div class="grid grid-cols-1 gap-3 md:grid-cols-2">

                        <div>
                            <label class="neo-label">
                                Option A
                                <span class="text-red-500">*</span>
                            </label>
                            <input
                                type="text"
                                name="option_a_new_${index}"
                                maxlength="500"
                                class="neo-input"
                                placeholder="Enter Option A">
                        </div>

                        <div>
                            <label class="neo-label">
                                Option B
                                <span class="text-red-500">*</span>
                            </label>
                            <input
                                type="text"
                                name="option_b_new_${index}"
                                maxlength="500"
                                class="neo-input"
                                placeholder="Enter Option B">
                        </div>

                        <div>
                            <label class="neo-label">
                                Option C
                                <span class="text-red-500">*</span>
                            </label>
                            <input
                                type="text"
                                name="option_c_new_${index}"
                                maxlength="500"
                                class="neo-input"
                                placeholder="Enter Option C">
                        </div>

                        <div>
                            <label class="neo-label">
                                Option D
                                <span class="text-red-500">*</span>
                            </label>
                            <input
                                type="text"
                                name="option_d_new_${index}"
                                maxlength="500"
                                class="neo-input"
                                placeholder="Enter Option D">
                        </div>

                    </div>

                    <div class="rounded-xl border border-emerald-100 bg-emerald-50/40 p-3">

                        <p class="mb-2 text-xs font-black text-slate-800">
                            Correct Answer
                            <span class="text-red-500">*</span>
                        </p>

                        <div class="grid grid-cols-2 gap-2 sm:grid-cols-4">

                            <label class="quiz-answer-option flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2.5 text-xs font-bold" data-answer-label="A">
                                <input type="radio" name="correct_answer_new_${index}" value="A" class="h-4 w-4">
                                <span>Option A</span>
                                <span class="quiz-answer-state correct">
                                    <i class="ri-check-line"></i>
                                    Correct
                                </span>
                                <span class="quiz-answer-state wrong">
                                    <i class="ri-close-line"></i>
                                    Wrong
                                </span>
                            </label>

                            <label class="quiz-answer-option flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2.5 text-xs font-bold" data-answer-label="B">
                                <input type="radio" name="correct_answer_new_${index}" value="B" class="h-4 w-4">
                                <span>Option B</span>
                                <span class="quiz-answer-state correct">
                                    <i class="ri-check-line"></i>
                                    Correct
                                </span>
                                <span class="quiz-answer-state wrong">
                                    <i class="ri-close-line"></i>
                                    Wrong
                                </span>
                            </label>

                            <label class="quiz-answer-option flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2.5 text-xs font-bold" data-answer-label="C">
                                <input type="radio" name="correct_answer_new_${index}" value="C" class="h-4 w-4">
                                <span>Option C</span>
                                <span class="quiz-answer-state correct">
                                    <i class="ri-check-line"></i>
                                    Correct
                                </span>
                                <span class="quiz-answer-state wrong">
                                    <i class="ri-close-line"></i>
                                    Wrong
                                </span>
                            </label>

                            <label class="quiz-answer-option flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2.5 text-xs font-bold" data-answer-label="D">
                                <input type="radio" name="correct_answer_new_${index}" value="D" class="h-4 w-4">
                                <span>Option D</span>
                                <span class="quiz-answer-state correct">
                                    <i class="ri-check-line"></i>
                                    Correct
                                </span>
                                <span class="quiz-answer-state wrong">
                                    <i class="ri-close-line"></i>
                                    Wrong
                                </span>
                            </label>

                        </div>

                    </div>

                </div>
            `;

            return block;

        }


        getQuestionCards().forEach(function (card) {

            attachDeleteHandler(card);
            attachNewQuestionRemoveHandler(card);
            attachAnswerVisualHandler(card);

        });


        addButton.addEventListener(
            "click",
            function () {

                const index =
                    nextNewIndex++;

                const block =
                    createNewQuestionBlock(index);

                container.appendChild(block);

                attachNewQuestionRemoveHandler(block);
                attachAnswerVisualHandler(block);

                updateQuestionNumbers();

                getQuestionCards().forEach(
                    updateDeleteState
                );

                block.scrollIntoView({
                    behavior: "smooth",
                    block: "center"
                });

                const firstInput =
                    block.querySelector("textarea");

                if (firstInput) {
                    firstInput.focus();
                }

            }
        );


        if (marksInput) {

            marksInput.addEventListener(
                "input",
                function () {
                    updateTotal(
                        getActiveQuestionCards().length
                    );
                }
            );

        }


        updateQuestionNumbers();

        getQuestionCards().forEach(
            updateDeleteState
        );

    });


    /* =======================================================
       MODAL HELPERS
    ======================================================= */

    function openModal(id) {

        const modal = document.getElementById(id);

        if (!modal) {
            return;
        }

        modal.classList.add("open");

        if (id === "quizModal") {
            window.dispatchEvent(new Event("quizModalOpened"));
        }

    }


    function closeModal(id) {

        const modal = document.getElementById(id);

        if (!modal) {
            return;
        }

        modal.classList.remove("open");

    }


    document.querySelectorAll("[data-close-modal]").forEach(function (button) {

        button.addEventListener("click", function () {

            closeModal(button.dataset.closeModal);

        });

    });


    document.querySelectorAll(".modal-overlay").forEach(function (overlay) {

        overlay.addEventListener("click", function (event) {

            if (event.target === overlay) {

                overlay.classList.remove("open");

            }

        });

    });


    /* =======================================================
       CHAPTER CREATE
    ======================================================= */

    const chapterButton =
        document.getElementById("openChapterModal");

    const emptyChapterButton =
        document.getElementById("emptyCreateChapterBtn");


    if (chapterButton) {

        chapterButton.addEventListener("click", function () {

            openModal("chapterModal");

        });

    }


    if (emptyChapterButton) {

        emptyChapterButton.addEventListener("click", function () {

            openModal("chapterModal");

        });

    }


    if (builderConfig.dataset.chapterFormErrors === "1") {

        openModal("chapterModal");

    }


    /* =======================================================
       CREATE MODALS
       JavaScript only opens/closes UI.
       All form actions, values and validation are server-side.
    ======================================================= */

    const createModalButtons = [
        ["openVideoUploadModal", "videoModal"],
        ["emptyVideoUploadBtn", "videoModal"],
        ["openPdfUploadModal", "pdfModal"],
        ["emptyPdfUploadBtn", "pdfModal"],
        ["openQuizModal", "quizModal"],
        ["emptyQuizBtn", "quizModal"],
    ];

    createModalButtons.forEach(function (item) {
        const button = document.getElementById(item[0]);
        if (button) {
            button.addEventListener("click", function () {
                openModal(item[1]);
            });
        }
    });

    if (builderConfig.dataset.videoCreateOpen === "1") {

        openModal("videoModal");

    }

    if (builderConfig.dataset.pdfCreateOpen === "1") {

        openModal("pdfModal");

    }

    if (builderConfig.dataset.quizCreateOpen === "1") {

        openModal("quizModal");

    }

    /* =======================================================
       SERVER-BOUND EDIT / DELETE MODALS
       Buttons contain only the modal id.
       No form action/value is changed here.
    ======================================================= */

    document.querySelectorAll("[data-open-modal]").forEach(function (button) {
        button.addEventListener("click", function (event) {
            event.stopPropagation();
            openModal(button.dataset.openModal);
        });
    });

    /* =======================================================
       THREE-DOT MENUS
       - Chapter menus open/close normally.
       - Video/PDF/Quiz menus are temporarily moved to BODY
         while open so internal scrolling and hover transforms
         cannot clip or hide them.
       - Timeline links remain normal Django navigation.
       - No form values or backend logic are changed here.
    ======================================================= */

    const openMenuState = {
        menu: null,
        button: null,
        parent: null,
    };


    function restoreOpenMenu() {

        const menu = openMenuState.menu;
        const parent = openMenuState.parent;

        if (menu && parent) {

            menu.classList.add("hidden");

            menu.style.position = "";
            menu.style.left = "";
            menu.style.top = "";
            menu.style.zIndex = "";

            parent.appendChild(menu);

        }

        openMenuState.menu = null;
        openMenuState.button = null;
        openMenuState.parent = null;

    }


    function closeAllMenus() {

        document.querySelectorAll(".menu").forEach(function (menu) {

            if (menu === openMenuState.menu) {
                return;
            }

            menu.classList.add("hidden");

        });

        restoreOpenMenu();

    }


    function positionFloatingMenu(menu, button) {

        if (!menu || !button) {
            return;
        }

        menu.classList.remove("hidden");

        /*
         * First move it to BODY. This is important because a video
         * card has a hover transform and the builder panels have
         * overflow scrolling. A fixed element inside such a parent
         * can still be clipped or visually disappear.
         */
        if (menu.parentElement !== document.body) {
            openMenuState.parent = menu.parentElement;
            document.body.appendChild(menu);
        }

        openMenuState.menu = menu;
        openMenuState.button = button;

        menu.style.position = "fixed";
        menu.style.zIndex = "99999";

        const buttonRect = button.getBoundingClientRect();

        const menuWidth = Math.min(
            180,
            Math.max(140, window.innerWidth - 16)
        );

        /*
         * The menu must be measurable before calculating its final
         * top position.
         */
        menu.style.width = menuWidth + "px";
        menu.style.left = "0px";
        menu.style.top = "0px";

        const menuRect = menu.getBoundingClientRect();

        let left = buttonRect.right - menuRect.width;
        let top = buttonRect.bottom + 6;

        if (left < 8) {
            left = 8;
        }

        if (left + menuRect.width > window.innerWidth - 8) {
            left = window.innerWidth - menuRect.width - 8;
        }

        if (top + menuRect.height > window.innerHeight - 8) {
            top = buttonRect.top - menuRect.height - 6;
        }

        if (top < 8) {
            top = 8;
        }

        menu.style.left = left + "px";
        menu.style.top = top + "px";

    }


    document.querySelectorAll(
        ".chapter-menu-button, .content-menu-button"
    ).forEach(function (button) {

        button.addEventListener("click", function (event) {

            event.preventDefault();
            event.stopPropagation();

            const isContentMenu =
                button.classList.contains("content-menu-button");

            /*
             * A video's three-dot menu belongs to that exact video.
             * Selecting its menu also selects the video so the
             * Information card and Edit Video button stay synchronized.
             */
            if (isContentMenu) {

                const videoCard =
                    button.closest("[data-video-selector]");

                if (videoCard) {
                    updateSelectedVideo(videoCard);
                }

            }

            let menu = null;

            /*
             * If this is the currently open floating menu, the same
             * three-dot button closes it.
             */
            if (
                openMenuState.menu &&
                openMenuState.button === button
            ) {
                closeAllMenus();
                return;
            }

            /*
             * Close another open menu first.
             */
            closeAllMenus();

            /*
             * After restore, the menu is back beside its button.
             */
            if (button.parentElement) {
                menu = button.parentElement.querySelector(".menu");
            }

            if (!menu) {
                return;
            }

            /*
             * Content menus are the important case for video/PDF/quiz.
             * Chapter menus also use the same safe positioning, so
             * every three-dot menu behaves consistently.
             */
            if (isContentMenu || button.classList.contains("chapter-menu-button")) {
                positionFloatingMenu(menu, button);
            }

        });

    });


    /*
     * When an Edit/Delete modal action is clicked, close the floating
     * menu first and restore it to its original location.
     *
     * Timeline <a> links are deliberately NOT intercepted. They
     * navigate normally to Django with ?view=...&item=....
     */
    document.querySelectorAll(".menu-item").forEach(function (item) {

        item.addEventListener("click", function () {

            if (
                item.matches("[data-open-modal]") &&
                openMenuState.menu &&
                openMenuState.menu.contains(item)
            ) {
                restoreOpenMenu();
            }

        });

    });


    /*
     * Scroll closes the menu because the button may move while its
     * internal builder panel is scrolling.
     */
    document.querySelectorAll(".builder-scroll").forEach(
        function (scrollArea) {

            scrollArea.addEventListener(
                "scroll",
                function () {
                    closeAllMenus();
                },
                { passive: true }
            );

        }
    );


    window.addEventListener("resize", function () {

        closeAllMenus();

    });


    document.addEventListener("click", function (event) {

        if (
            event.target.closest(
                ".chapter-menu-button, .content-menu-button, .menu"
            )
        ) {
            return;
        }

        closeAllMenus();

    });


    /* =======================================================
       DELETE
       Delete forms already contain their final Django action.
    ======================================================= */

    /* =======================================================
       ESCAPE KEY
    ======================================================= */

    document.addEventListener("keydown", function (event) {

        if (event.key !== "Escape") {
            return;
        }

        document.querySelectorAll(".modal-overlay.open").forEach(
            function (modal) {

                modal.classList.remove("open");

            }
        );

        document.querySelectorAll(".menu").forEach(
            function (menu) {

                menu.classList.add("hidden");

            }
        );

    });


    /* =======================================================
       AUTO DISMISS MESSAGES / FORM ERRORS
       Success messages, form-level errors, and field-level
       validation errors disappear after 5 seconds.
    ======================================================= */

    function autoDismissMessage(element) {

        if (!element) {
            return;
        }

        element.classList.add("form-auto-dismiss");

        element.style.transition =
            "opacity .35s ease, transform .35s ease, " +
            "max-height .35s ease, margin .35s ease, padding .35s ease";

        element.style.opacity = "0";
        element.style.transform = "translateY(-8px)";

        setTimeout(function () {

            element.remove();

        }, 400);

    }


    setTimeout(function () {

        document.querySelectorAll(
            ".message-box, .form-error-box, .field-error"
        ).forEach(function (message) {

            autoDismissMessage(message);

        });

    }, 5000);


    /* =======================================================
       PRESERVE LEFT CURRICULUM SCROLL
       Chapter/workspace links perform normal Django GET refreshes,
       but the curriculum scroll position remains stable.
    ======================================================= */

    const curriculumScroll =
        document.querySelector(".curriculum-panel .builder-scroll");

    const curriculumScrollKey =
        "neolearn_course_builder_curriculum_scroll";

    if (curriculumScroll) {

        const savedScroll =
            sessionStorage.getItem(curriculumScrollKey);

        if (savedScroll !== null) {

            const scrollValue =
                parseInt(savedScroll, 10);

            if (!Number.isNaN(scrollValue)) {

                curriculumScroll.scrollTop =
                    scrollValue;

            }

        }

        document.querySelectorAll(
            ".curriculum-panel .builder-scroll a"
        ).forEach(function (link) {

            link.addEventListener("click", function () {

                sessionStorage.setItem(
                    curriculumScrollKey,
                    String(curriculumScroll.scrollTop)
                );

            });

        });

    }

});