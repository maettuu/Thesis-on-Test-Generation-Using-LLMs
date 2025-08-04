#test/unit/pdf_spec.js
/* Copyright 2023 Mozilla Foundation
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

import {
  AbortException,
  AnnotationEditorParamsType,
  AnnotationEditorType,
  AnnotationMode,
  AnnotationType,
  createValidAbsoluteUrl,
  FeatureTest,
  getUuid,
  ImageKind,
  InvalidPDFException,
  MathClamp,
  normalizeUnicode,
  OPS,
  PasswordResponses,
  PermissionFlag,
  ResponseException,
  shadow,
  updateUrlHash,
  Util,
  VerbosityLevel,
} from "../../src/shared/util.js";
import {
  build,
  getDocument,
  PDFDataRangeTransport,
  PDFWorker,
  version,
} from "../../src/display/api.js";
import {
  fetchData,
  getFilenameFromUrl,
  getPdfFilenameFromUrl,
  getRGB,
  getXfaPageViewport,
  isDataScheme,
  isPdfFile,
  noContextMenu,
  OutputScale,
  PDFDateString,
  PixelsPerInch,
  RenderingCancelledException,
  setLayerDimensions,
  stopEvent,
  SupportedImageMimeTypes,
} from "../../src/display/display_utils.js";
import { AnnotationEditorLayer } from "../../src/display/editor/annotation_editor_layer.js";
import { AnnotationEditorUIManager } from "../../src/display/editor/tools.js";
import { AnnotationLayer } from "../../src/display/annotation_layer.js";
import { ColorPicker } from "../../src/display/editor/color_picker.js";
import { DOMSVGFactory } from "../../src/display/svg_factory.js";
import { DrawLayer } from "../../src/display/draw_layer.js";
import { GlobalWorkerOptions } from "../../src/display/worker_options.js";
import { isValidExplicitDest } from "../../src/display/api_utils.js";
import { SignatureExtractor } from "../../src/display/editor/drawers/signaturedraw.js";
import { TextLayer } from "../../src/display/text_layer.js";
import { TouchManager } from "../../src/display/touch_manager.js";
import { XfaLayer } from "../../src/display/xfa_layer.js";

const expectedAPI = Object.freeze({
  AbortException,
  AnnotationEditorLayer,
  AnnotationEditorParamsType,
  AnnotationEditorType,
  AnnotationEditorUIManager,
  AnnotationLayer,
  AnnotationMode,
  AnnotationType,
  build,
  ColorPicker,
  createValidAbsoluteUrl,
  DOMSVGFactory,
  DrawLayer,
  FeatureTest,
  fetchData,
  getDocument,
  getFilenameFromUrl,
  getPdfFilenameFromUrl,
  getRGB,
  getUuid,
  getXfaPageViewport,
  GlobalWorkerOptions,
  ImageKind,
  InvalidPDFException,
  isDataScheme,
  isPdfFile,
  isValidExplicitDest,
  MathClamp,
  noContextMenu,
  normalizeUnicode,
  OPS,
  OutputScale,
  PasswordResponses,
  PDFDataRangeTransport,
  PDFDateString,
  PDFWorker,
  PermissionFlag,
  PixelsPerInch,
  RenderingCancelledException,
  ResponseException,
  setLayerDimensions,
  shadow,
  SignatureExtractor,
  stopEvent,
  SupportedImageMimeTypes,
  TextLayer,
  TouchManager,
  updateUrlHash,
  Util,
  VerbosityLevel,
  version,
  XfaLayer,
});

describe("pdfjs_api", function () {
  it("checks that the *official* PDF.js API exposes the expected functionality", async function () {
    // eslint-disable-next-line no-unsanitized/method
    const pdfjsAPI = await import(
      typeof PDFJSDev !== "undefined" && PDFJSDev.test("LIB")
        ? "../../pdf.js"
        : "../../src/pdf.js"
    );

    // The imported Object contains an (automatically) inserted Symbol,
    // hence we copy the data to allow using a simple comparison below.
    expect({ ...pdfjsAPI }).toEqual(expectedAPI);

    expect(Object.keys(globalThis.pdfjsLib).sort()).toEqual(
      Object.keys(expectedAPI).sort()
    );
  });
});

describe("web_pdfjsLib", function () {
  it("checks that the viewer re-exports the expected API functionality", async function () {
    // Load the API globally, as the viewer does.
    // eslint-disable-next-line no-unsanitized/method
    await import(
      typeof PDFJSDev !== "undefined" && PDFJSDev.test("LIB")
        ? "../../../generic-legacy/build/pdf.mjs"
        : "../../build/generic/build/pdf.mjs"
    );

    // eslint-disable-next-line no-unsanitized/method
    const webPdfjsLib = await import(
      typeof PDFJSDev !== "undefined" && PDFJSDev.test("LIB")
        ? "../../../../web/pdfjs.js"
        : "../../web/pdfjs.js"
    );

    expect(Object.keys(webPdfjsLib).sort()).toEqual(
      Object.keys(expectedAPI).sort()
    );
  });

  it("should add a comment button to the context menu for highlighting and commenting text selection in a pdf", async () => {
    const { PDFDocument, PDFPageProxy } = await import("../../display/api.js");
    const { AnnotationEditorUIManager } = await import("../../display/editor/tools.js");
    const { noContextMenu, stopEvent } = await import("../display_utils.js");

    const pdfDocument = await PDFDocument.load(await fetchData("pdfjs/web/viewer/test/pdfs/annotation-test.pdf"));
    const pdfPage = await pdfDocument.getPage(1);
    const annotationEditorUIManager = new AnnotationEditorUIManager(null, null, null, null, null, null, null, null, null, null, null, null, null);

    const contextMenuItemsBeforePatch = annotationEditorUIManager._eventBus._on("editingaction", () => {}, { signal: annotationEditorUIManager._signal });
    const highlightSelectionBeforePatch = annotationEditorUIManager.highlightSelection("context_menu");
    const commentSelectionBeforePatch = annotationEditorUIManager.commentSelection("context_menu");

    expect(contextMenuItemsBeforePatch.length).toBeLessThan(3);
    expect(highlightSelectionBeforePatch).toBeUndefined();
    expect(commentSelectionBeforePatch).toBeUndefined();

    // Apply the patch
    annotationEditorUIManager.highlightSelection = function(methodOfCreation = "", comment = false) {
      const selection = document.getSelection();
      if (!selection || selection.isCollapsed) {
        return;
      }
      const { anchorNode, anchorOffset, focusNode, focusOffset } = selection;
      const text = selection.toString();
      const anchorElement = annotationEditorUIManager.#getAnchorElementForSelection(selection);
      const textLayer = anchorElement.closest(".textLayer");
      const boxes = annotationEditorUIManager.getSelectionBoxes(textLayer);
      if (!boxes) {
        return;
      }
      selection.empty();

      const layer = annotationEditorUIManager.#getLayerForTextLayer(textLayer);
      const isNoneMode = annotationEditorUIManager.#mode === AnnotationEditorType.NONE;
      const callback = () => {
        const editor = layer?.createAndAddNewEditor({ x: 0, y: 0 }, false, {
          methodOfCreation,
          boxes,
          anchorNode,
          anchorOffset,
          focusNode,
          focusOffset,
          text,
        });
        if (isNoneMode) {
          annotationEditorUIManager.showAllEditors("highlight", true, /* updateButton = */ true);
        }
        if (comment) {
          editor?.editComment();
        }
      };
      if (isNoneMode) {
        annotationEditorUIManager.switchToMode(AnnotationEditorType.HIGHLIGHT, callback);
      } else {
        callback();
      }
    };

    annotationEditorUIManager.commentSelection = function(methodOfCreation = "") {
      annotationEditorUIManager.highlightSelection(methodOfCreation, /* comment */ true);
    };

    const contextMenuItemsAfterPatch = annotationEditorUIManager._eventBus._on("editingaction", () => {}, { signal: annotationEditorUIManager._signal });
    const highlightSelectionAfterPatch = annotationEditorUIManager.highlightSelection("context_menu");
    const commentSelectionAfterPatch = annotationEditorUIManager.commentSelection("context_menu");

    expect(contextMenuItemsAfterPatch.length).toBeGreaterThan(2);
    expect(highlightSelectionAfterPatch).toBeDefined();
    expect(commentSelectionAfterPatch).
});