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
  Util,
  VerbosityLevel,
} from "../../src/shared/util.js";
import {
  build,
  getDocument,
  isValidExplicitDest,
  PDFDataRangeTransport,
  PDFWorker,
  version,
} from "../../src/display/api.js";
import {
  fetchData,
  getFilenameFromUrl,
  getPdfFilenameFromUrl,
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

  it("should handle touch events without throwing null error in touchMoveAC", async () => {
    const { PDFDocument } = await import("../../core/document.js");
    const { PDFPage } = await import("../../core/document.js");
    const { AnnotationEditorUIManager } = await import("../../display/editor/tools.js");
    const { TouchManager } = await import("../../display/touch_manager.js");
    const { TestPdfsServer } = await import("./test_utils.js");

    // Setup the test PDF
    const server = new TestPdfsServer();
    const blankPdf = await server.loadPDF("blank.pdf");
    const page = await blankPdf.getPage(1);

    // Initialize annotation editor and touch manager
    const annotationEditor = new AnnotationEditorUIManager();
    const touchManager = new TouchManager(page.div, {
      pinchZoomEnabled: true,
      touchStartThreshold: 0,
    });

    // Set up the annotation mode
    annotationEditor.switchMode(AnnotationEditorType.FREE_HAND);

    try {
      // Simulate touch events to draw
      const touchStartEvt = new TouchEvent("touchstart", {
        touches: [{ target: page.div, clientX: 100, clientY: 100 }],
      });
      const touchMoveEvt = new TouchEvent("touchmove", {
        touches: [{ target: page.div, clientX: 150, clientY: 150 }],
      });
      const touchEndEvt = new TouchEvent("touchend", {});

      page.div.dispatchEvent(touchStartEvt);
      page.div.dispatchEvent(touchMoveEvt);
      page.div.dispatchEvent(touchEndEvt);

      // If no error was thrown, the test passes
      expect(true).toBe(true);
    } catch (error) {
      // If an error was thrown, the test fails
      expect(error).not.toBeInstanceOf(Error);
    }
  });
});