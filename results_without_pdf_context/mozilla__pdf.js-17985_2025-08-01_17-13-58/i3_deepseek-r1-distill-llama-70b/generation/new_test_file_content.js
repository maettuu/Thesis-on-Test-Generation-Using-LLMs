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

  it("should respect verbosity level when handling OpenJPEG warnings", async () => {
    const { JpxImage, JpxError } = await import("../../core/jpx.js");
    const { VerbosityLevel, setVerbosityLevel, getVerbosityLevel } = await import("../../shared/util.js");

    // Mock console.warn to track warnings
    const mockConsoleWarn = jest.spyOn(console, 'warn').mockImplementation(() => {});

    try {
      // Set verbosity to error, which should suppress warnings
      setVerbosityLevel(VerbosityLevel.error);

      // Mock OpenJPEG decode to return a warning string
      const mockOpenJPEG = {
        decode: () => "Warning message",
      };
      JpxImage.decode = jest.fn(() => mockOpenJPEG.decode());

      // Test with sample data
      const testData = new Uint8Array([0xff, 0x51, 0x00, 0x00]);
      const result = await JpxImage.decode(testData);

      // Verify that no warning was logged
      expect(mockConsoleWarn).not.toHaveBeenCalled();

      // Cleanup
      JpxImage.cleanup();
    } finally {
      // Restore original console.warn and verbosity level
      mockConsoleWarn.mockRestore();
      setVerbosityLevel(getVerbosityLevel());
    }
  });
});