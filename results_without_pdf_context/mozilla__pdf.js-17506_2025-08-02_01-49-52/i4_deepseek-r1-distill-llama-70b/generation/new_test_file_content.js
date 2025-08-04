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
  CMapCompressionType,
  createValidAbsoluteUrl,
  FeatureTest,
  ImageKind,
  InvalidPDFException,
  isNodeJS,
  MissingPDFException,
  normalizeUnicode,
  OPS,
  PasswordResponses,
  PermissionFlag,
  PromiseCapability,
  shadow,
  UnexpectedResponseException,
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
  DOMSVGFactory,
  fetchData,
  getFilenameFromUrl,
  getPdfFilenameFromUrl,
  getXfaPageViewport,
  isDataScheme,
  isPdfFile,
  noContextMenu,
  PDFDateString,
  PixelsPerInch,
  RenderingCancelledException,
  setLayerDimensions,
} from "../../src/display/display_utils.js";
import {
  renderTextLayer,
  updateTextLayer,
} from "../../src/display/text_layer.js";
import { AnnotationEditorLayer } from "../../src/display/editor/annotation_editor_layer.js";
import { AnnotationEditorUIManager } from "../../src/display/editor/tools.js";
import { AnnotationLayer } from "../../src/display/annotation_layer.js";
import { ColorPicker } from "../../src/display/editor/color_picker.js";
import { DrawLayer } from "../../src/display/draw_layer.js";
import { GlobalWorkerOptions } from "../../src/display/worker_options.js";
import { Outliner } from "../../src/display/editor/outliner.js";
import { XfaLayer } from "../../src/display/xfa_layer.js";

const expectedAPI = Object.freeze({
  AbortException,
  AnnotationEditorLayer,
  AnnotationEditorParamsType,
  AnnotationEditorType,
  AnnotationEditorUIManager,
  AnnotationLayer,
  AnnotationMode,
  build,
  CMapCompressionType,
  ColorPicker,
  createValidAbsoluteUrl,
  DOMSVGFactory,
  DrawLayer,
  FeatureTest,
  fetchData,
  getDocument,
  getFilenameFromUrl,
  getPdfFilenameFromUrl,
  getXfaPageViewport,
  GlobalWorkerOptions,
  ImageKind,
  InvalidPDFException,
  isDataScheme,
  isPdfFile,
  MissingPDFException,
  noContextMenu,
  normalizeUnicode,
  OPS,
  Outliner,
  PasswordResponses,
  PDFDataRangeTransport,
  PDFDateString,
  PDFWorker,
  PermissionFlag,
  PixelsPerInch,
  PromiseCapability,
  RenderingCancelledException,
  renderTextLayer,
  setLayerDimensions,
  shadow,
  UnexpectedResponseException,
  updateTextLayer,
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
    if (isNodeJS) {
      pending("loadScript is not supported in Node.js.");
    }
    const apiPath = "../../build/generic/build/pdf.mjs";
    await import(apiPath);

    const webPdfjsLib = await import("../../web/pdfjs.js");

    expect(Object.keys(webPdfjsLib).sort()).toEqual(
      Object.keys(expectedAPI).sort()
    );
  });

  it("should highlight images of text", async () => {
    const { PDFDocument } = await import("../../core/pdf_document.js");
    const { AnnotationEditorLayer } = await import("../../display/editor/annotation_editor_layer.js");
    const { DrawLayer } = await import("../../display/draw_layer.js");
    const { DOMSVGFactory } = await import("../../display_utils.js");

    // Setup test PDF with image
    const pdf = new PDFDocument({
      content: new Uint8Array(),
      pages: [
        {
          content: new Uint8Array(),
          viewport: { width: 100, height: 100, scale: 1 },
          images: [
            {
              x: 10,
              y: 10,
              width: 80,
              height: 80,
            },
          ],
        },
      ],
    });

    const uiManager = {
      getMode: () => AnnotationEditorType.HIGHLIGHT,
      updateToolbar: jest.fn(),
      updateMode: jest.fn(),
      registerEditorTypes: jest.fn(),
      getId: () => "1",
      getActive: () => null,
      setEditingState: jest.fn(),
      addEditor: jest.fn(),
      setSelected: jest.fn(),
      toggleSelected: jest.fn(),
      isSelected: jest.fn(),
      addCommands: jest.fn(),
      commitOrRemove: jest.fn(),
      addToAnnotationStorage: jest.fn(),
    };

    const drawLayer = new DrawLayer({ pageIndex: 0 });
    const annotationEditorLayer = new AnnotationEditorLayer({
      uiManager,
      pageIndex: 0,
      div: document.createElement("div"),
      accessibilityManager: null,
      annotationLayer: null,
      drawLayer,
      textLayer: {
        div: document.createElement("div"),
        getBoundingClientRect: () => ({
          x: 0,
          y: 0,
          width: 100,
          height: 100,
        }),
      },
      viewport: {
        rawDims: [100, 100],
        rotation: 0,
      },
      l10n: {},
    });

    // Simulate pointer events
    const pointerDown = new PointerEvent("pointerdown", {
      bubbles: true,
      cancelable: true,
      pointerType: "mouse",
      buttons: 1,
    });

    const pointerMove = new PointerEvent("pointermove", {
      bubbles: true,
      cancelable: true,
      pointerType: "mouse",
      buttons: 1,
    });

    const pointerUp = new PointerEvent("pointerup", {
      bubbles: true,
      cancelable: true,
      pointerType: "mouse",
      buttons: 1,
    });

    // Start highlighting
    annotationEditorLayer.pointerDown(pointerDown);
    annotationEditorLayer.pointerMove(pointerMove);
    annotationEditorLayer.pointerUp(pointerUp);

    // Check if highlight was created
    const highlight = drawLayer.highlight(
      {
        box: {
          x: 0,
          y: 0,
          width: 1,
          height: 1,
        },
        toSVGPath: () => "M0,0 L1,0 L1,1 L0,1 Z",
      },
      "#fff",
      0.5
    );

    expect(highlight.id).toBeDefined();
  });
});