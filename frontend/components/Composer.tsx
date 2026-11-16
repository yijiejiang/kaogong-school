"use client";

import { ArrowUp, Loader2, Mic, Paperclip, Square } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { transcribeAudio } from "@/lib/api";

type ComposerProps = {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  onStop: () => void;
  onFile: (file: File) => void;
  streaming: boolean;
  disabled?: boolean;
};

export function Composer({
  value,
  onChange,
  onSend,
  onStop,
  onFile,
  streaming,
  disabled = false,
}: ComposerProps) {
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const valueRef = useRef(value);
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [micError, setMicError] = useState<string | null>(null);

  valueRef.current = value;

  useEffect(() => {
    const node = textareaRef.current;
    if (!node) return;
    node.style.height = "0px";
    node.style.height = `${Math.min(node.scrollHeight, 168)}px`;
  }, [value]);

  useEffect(() => {
    return () => {
      recorderRef.current?.stop();
      streamRef.current?.getTracks().forEach((track) => track.stop());
    };
  }, []);

  const stopRecording = () => {
    recorderRef.current?.stop();
    setRecording(false);
  };

  const startRecording = async () => {
    setMicError(null);
    if (
      typeof navigator === "undefined" ||
      !navigator.mediaDevices?.getUserMedia ||
      typeof MediaRecorder === "undefined"
    ) {
      setMicError("当前浏览器不支持录音，请用 Chrome / Safari 最新版。");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const mimeType = MediaRecorder.isTypeSupported("audio/webm")
        ? "audio/webm"
        : MediaRecorder.isTypeSupported("audio/mp4")
          ? "audio/mp4"
          : "";
      const recorder = new MediaRecorder(
        stream,
        mimeType ? { mimeType } : undefined,
      );
      chunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };
      recorder.onstop = () => {
        stream.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
        const blob = new Blob(chunksRef.current, {
          type: recorder.mimeType || "audio/webm",
        });
        chunksRef.current = [];
        if (blob.size === 0) return;
        const extension = (recorder.mimeType || "").includes("mp4")
          ? "m4a"
          : "webm";
        const file = new File([blob], `voice-${Date.now()}.${extension}`, {
          type: recorder.mimeType || "audio/webm",
        });
        setTranscribing(true);
        transcribeAudio(file)
          .then((result) => {
            const text = result.text.trim();
            if (!text) {
              setMicError("没有识别到语音内容，请再试一次。");
              return;
            }
            const current = valueRef.current;
            onChange(current ? `${current}${current.endsWith(" ") ? "" : " "}${text}` : text);
          })
          .catch((error) =>
            setMicError(
              error instanceof Error ? error.message : "语音转写失败",
            ),
          )
          .finally(() => setTranscribing(false));
      };
      recorder.start();
      recorderRef.current = recorder;
      setRecording(true);
    } catch (error) {
      setMicError(
        error instanceof Error
          ? `无法使用麦克风：${error.message}`
          : "无法使用麦克风",
      );
    }
  };

  return (
    <div className="shrink-0 border-t border-line bg-[#f7f4ee]/90 px-3 pb-3 pt-3 backdrop-blur sm:px-6 sm:pb-5">
      <div className="mx-auto w-full max-w-3xl">
        <div className="flex items-end gap-2 rounded-2xl border border-line bg-paper p-2 shadow-[0_2px_12px_rgba(31,35,40,0.04)] focus-within:border-[#cfc4b5]">
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            title="上传资料"
            className="mb-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-[#8a8475] transition hover:bg-[#f3efe7]"
          >
            <Paperclip className="h-4 w-4" />
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,.txt,.md,.markdown,.png,.jpg,.jpeg,.webp,.mp3,.m4a,.wav,.aac,.flac,.ogg,.webm,.mp4"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) onFile(file);
              event.target.value = "";
            }}
          />

          <button
            type="button"
            onClick={() => {
              if (recording) stopRecording();
              else void startRecording();
            }}
            disabled={transcribing || disabled || streaming}
            title={recording ? "停止录音并转写" : "语音输入"}
            className={`mb-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl transition disabled:opacity-50 ${
              recording
                ? "bg-red-500 text-white"
                : "text-[#8a8475] hover:bg-[#f3efe7]"
            }`}
          >
            {transcribing ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Mic className="h-4 w-4" />
            )}
          </button>

          <textarea
            ref={textareaRef}
            rows={1}
            value={value}
            onChange={(event) => onChange(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                if (!disabled && value.trim() && !streaming) onSend();
              }
            }}
            placeholder={
              disabled
                ? "请先在设置中配置 LLM 模型…"
                : "问辅导员，或者说出你想做的事…"
            }
            className="max-h-[168px] min-h-[40px] flex-1 resize-none bg-transparent px-1 py-2 text-sm leading-6 text-ink outline-none placeholder:text-[#a59d90]"
          />

          {streaming ? (
            <button
              type="button"
              onClick={onStop}
              title="停止生成"
              className="mb-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-ink text-white transition hover:opacity-90"
            >
              <Square className="h-3.5 w-3.5 fill-current" />
            </button>
          ) : (
            <button
              type="button"
              onClick={onSend}
              disabled={disabled || !value.trim()}
              title="发送"
              className="mb-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-accent text-white transition enabled:hover:opacity-90 disabled:cursor-not-allowed disabled:bg-[#d8d0c4] disabled:text-[#9f9688]"
            >
              <ArrowUp className="h-4 w-4" />
            </button>
          )}
        </div>

        <div className="mt-2 flex flex-wrap items-center justify-between gap-2 px-1 text-[10px] text-muted">
          <span>
            {micError
              ? micError
              : transcribing
                ? "正在把语音转成文字…"
                : recording
                  ? "正在录音，再点一次麦克风结束"
                  : "上传 PDF / Word / Markdown / 图片 / 音频 · Enter 发送"}
          </span>
          <span>辅导员会按问题转接给合适的老师</span>
        </div>
      </div>
    </div>
  );
}
