#test/unit/stream_spec.js
/* Copyright 2017 Mozilla Foundation
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

import { Dict } from "../../src/core/primitives.js";
import { PredictorStream } from "../../src/core/predictor_stream.js";
import { Stream } from "../../src/core/stream.js";

describe("stream", function () {
  describe("PredictorStream", function () {
    it("should decode simple predictor data", function () {
      const dict = new Dict();
      dict.set("Predictor", 12);
      dict.set("Colors", 1);
      dict.set("BitsPerComponent", 8);
      dict.set("Columns", 2);

      const input = new Stream(
        new Uint8Array([2, 100, 3, 2, 1, 255, 2, 1, 255]),
        0,
        9,
        dict
      );
      const predictor = new PredictorStream(input, /* length = */ 9, dict);
      const result = predictor.getBytes(6);

      expect(result).toEqual(new Uint8Array([100, 3, 101, 2, 102, 1]));
    });
  });

  it("should handle streams sequence with filtering", async () => {
    const { StreamsSequenceStream, BaseStream } = await import("../../core/decode_stream.js");
    const testStream = new Stream(new Uint8Array([1, 2, 3, 4]));

    // Create a mix of valid and invalid streams
    const streams = [
      testStream,
      new Stream(new Uint8Array([5, 6, 7, 8])), // valid
      {}, // invalid, not a BaseStream
      new BaseStream() // valid
    ];

    const streamSequence = new StreamsSequenceStream(streams);
    const result = await streamSequence.getBytes();

    // Expected data from the valid streams (testStream and the second Stream)
    const expected = new Uint8Array([1, 2, 3, 4, 5, 6, 7, 8]);
    expect(result).toEqual(expected);
  });
});