#test/unit/pdf.image_decoders_spec.js
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
  getVerbosityLevel,
  setVerbosityLevel,
  VerbosityLevel,
} from "../../src/shared/util.js";
import { Jbig2Error, Jbig2Image } from "../../src/core/jbig2.js";
import { JpegError, JpegImage } from "../../src/core/jpg.js";
import { JpxError, JpxImage } from "../../src/core/jpx.js";

describe("pdfimage_api", function () {
  it("checks that the *official* PDF.js-image decoders API exposes the expected functionality", async function () {
    // eslint-disable-next-line no-unsanitized/method
    const pdfimageAPI = await import(
      typeof PDFJSDev !== "undefined" && PDFJSDev.test("LIB")
        ? "../../pdf.image_decoders.js"
        : "../../src/pdf.image_decoders.js"
    );

    // The imported Object contains an (automatically) inserted Symbol,
    // hence we copy the data to allow using a simple comparison below.
    expect({ ...pdfimageAPI }).toEqual({
      getVerbosityLevel,
      Jbig2Error,
      Jbig2Image,
      JpegError,
      JpegImage,
      JpxError,
      JpxImage,
      setVerbosityLevel,
      VerbosityLevel,
    });
  });

  it("should respect verbosity level when decoding JPX images", async () => {
    const { JpxImage, VerbosityLevel, setVerbosityLevel, getVerbosityLevel } = await import("../../shared/util.js");

    let warned = false;
    const originalWarn = console.warn;
    console.warn = (msg) => {
      if (msg.includes("OpenJPEG warning")) {
        warned = true;
      }
    };

    try {
      // Test with QUIET verbosity: should not warn
      setVerbosityLevel(VerbosityLevel.QUERY);
      await JpxImage.decode(new Uint8Array([0x00, 0x00, 0x00, 0x00])); // Invalid JPX data to trigger warning
      expect(warned).toBe(false);

      // Test with DEBUG verbosity: should warn
      setVerbosityLevel(VerbosityLevel.DEBUG);
      await JpxImage.decode(new Uint8Array([0x00, 0x00, 0x00, 0x00]));
      expect(warned).toBe(true);
    } finally {
      console.warn = originalWarn;
    }
  });


  it("should respect verbosity level when decoding JPX images", async () => {
    const { JpxImage, VerbosityLevel, setVerbosityLevel, getVerbosityLevel } = await import("../../shared/util.js");

    let warned = false;
    const originalWarn = console.warn;
    console.warn = (msg) => {
      if (msg.includes("OpenJPEG warning")) {
        warned = true;
      }
    };

    try {
      // Test with QUIET verbosity: should not warn
      setVerbosityLevel(VerbosityLevel.QUERY);
      await JpxImage.decode(new Uint8Array([0x00, 0x00, 0x00, 0x00])); // Invalid JPX data to trigger warning
      expect(warned).toBe(false);

      // Test with DEBUG verbosity: should warn
      setVerbosityLevel(VerbosityLevel.DEBUG);
      await JpxImage.decode(new Uint8Array([0x00, 0x00, 0x00, 0x00]));
      expect(warned).toBe(true);
    } finally {
      console.warn = originalWarn;
    }
  });
});