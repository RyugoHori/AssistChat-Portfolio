'use client';

import {
  KeyboardEvent,
  memo,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import {
  AlertCircle,
  Bot,
  Loader2,
  RotateCcw,
  Send,
  Sparkles,
  Square,
  User,
} from 'lucide-react';

import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';
import { CHAT_CONFIG } from '@/lib/constants';
import { useChat } from '@/hooks/useChat';
import { useSearchContext } from '@/contexts/SearchContext';
import {
  ChatConfidence,
  ChatSource,
  ChatUiMessage,
} from '@/types';

interface ChatModeProps {
  /** AI モードから検索結果タブに切り替える */
  onShowSearchResults: () => void;
  /** 引用元クリック時に呼ばれる */
  onResultClick?: (docId: string) => void;
}

const SAMPLE_PROMPTS = [
  'コンベアが停止した。原因と対処法を教えて',
  'モーターから異音がするときのチェックポイントは？',
  'リミットスイッチが効かない場合、まず何を確認すべき？',
];

/**
 * AI モード（会話型 RAG）
 *
 * - 会話履歴を保持し、過去のやり取りを踏まえた質問が可能
 * - バックエンドが Query Rewriting で独立検索クエリを生成
 * - 回答はトークン単位でストリーミング表示
 * - 引用元（sources）はメッセージごとに紐づいて表示される
 */
export function ChatMode({ onShowSearchResults, onResultClick }: ChatModeProps) {
  // 検索モードのフィルターを対話検索にも反映する
  const { filters, pendingAskAi, consumePendingAskAi } = useSearchContext();
  const { messages, isStreaming, sendMessage, resetChat, stopStreaming } = useChat({
    filters,
  });

  const [input, setInput] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // 新着メッセージ or ストリーミングで末尾に自動スクロール
  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' });
  }, [messages]);

  // 検索結果カードから「AI に質問」されたとき、起点事例を元に最初の質問を自動送信する
  useEffect(() => {
    if (!pendingAskAi || isStreaming) return;
    const seed = consumePendingAskAi();
    if (seed) {
      void sendMessage(seed.prompt);
    }
    // consume 後は pendingAskAi が null になるので、再発火しない
  }, [pendingAskAi, isStreaming, consumePendingAskAi, sendMessage]);

  const hasMessages = messages.length > 0;

  const handleSubmit = () => {
    const value = input.trim();
    if (!value || isStreaming) return;
    setInput('');
    void sendMessage(value);
    // Enter 連打で focus が外れないようにする
    requestAnimationFrame(() => inputRef.current?.focus());
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // Shift+Enter は改行、Enter 単独で送信（一般的なチャット UX）
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleSamplePrompt = (prompt: string) => {
    if (isStreaming) return;
    setInput('');
    void sendMessage(prompt);
  };

  const handleReset = () => {
    resetChat();
    setInput('');
    inputRef.current?.focus();
  };

  return (
    <div className="flex flex-col h-[70vh] sm:h-[75vh] min-h-[520px] bg-white rounded-lg border border-slate-200 shadow-sm overflow-hidden">
      {/* ヘッダー */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 bg-gradient-to-r from-blue-50 to-indigo-50">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center shadow-sm">
            <Sparkles className="h-4 w-4 text-white" />
          </div>
          <div>
            <div className="text-sm font-semibold text-slate-900">保全アシスタント</div>
            <div className="text-[11px] text-slate-500">過去の保全記録を根拠に回答します</div>
          </div>
        </div>
        <div className="flex items-center gap-1">
          {hasMessages && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleReset}
              disabled={isStreaming}
              className="text-slate-600 hover:text-slate-900"
            >
              <RotateCcw className="h-3.5 w-3.5 mr-1" />
              新しい会話
            </Button>
          )}
        </div>
      </div>

      {/* メッセージ一覧 */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto px-3 sm:px-5 py-4 space-y-4 bg-slate-50/50"
      >
        {!hasMessages ? (
          <EmptyState onSample={handleSamplePrompt} />
        ) : (
          messages.map((msg) => (
            <MessageBubble
              key={msg.id}
              message={msg}
              onResultClick={onResultClick}
              onShowSearchResults={onShowSearchResults}
            />
          ))
        )}
      </div>

      {/* 入力エリア */}
      <div className="border-t border-slate-200 bg-white px-3 sm:px-4 py-3">
        <div className="flex items-end gap-2">
          <Textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              isStreaming
                ? '回答生成中です…'
                : hasMessages
                  ? '追加の質問を入力（Enter で送信 / Shift+Enter で改行）'
                  : '故障内容や症状を入力してください'
            }
            maxLength={CHAT_CONFIG.MAX_MESSAGE_LENGTH}
            disabled={isStreaming}
            rows={1}
            className="flex-1 resize-none min-h-[44px] max-h-40 text-sm"
          />
          {isStreaming ? (
            <Button
              type="button"
              variant="outline"
              size="icon"
              onClick={stopStreaming}
              aria-label="生成を停止"
            >
              <Square className="h-4 w-4" />
            </Button>
          ) : (
            <Button
              type="button"
              size="icon"
              onClick={handleSubmit}
              disabled={!input.trim()}
              aria-label="送信"
            >
              <Send className="h-4 w-4" />
            </Button>
          )}
        </div>
        <div className="mt-1.5 flex items-center justify-between text-[11px] text-slate-500">
          <span>
            {input.length} / {CHAT_CONFIG.MAX_MESSAGE_LENGTH}
          </span>
          <span>AI の回答は参考情報です。重要な判断は原本を確認してください。</span>
        </div>
      </div>
    </div>
  );
}

// ==================== サブコンポーネント ====================

interface MessageBubbleProps {
  message: ChatUiMessage;
  onResultClick?: (docId: string) => void;
  onShowSearchResults: () => void;
}

const MessageBubble = memo(function MessageBubble({
  message,
  onResultClick,
  onShowSearchResults,
}: MessageBubbleProps) {
  const isUser = message.role === 'user';

  return (
    <div
      className={cn(
        'flex gap-2 sm:gap-3',
        isUser ? 'flex-row-reverse' : 'flex-row',
      )}
    >
      <Avatar role={message.role} />
      <div
        className={cn(
          'flex flex-col gap-2 max-w-[85%]',
          isUser ? 'items-end' : 'items-start',
        )}
      >
        <div
          className={cn(
            'rounded-2xl px-4 py-2.5 text-sm leading-relaxed shadow-sm',
            isUser
              ? 'bg-blue-600 text-white rounded-br-sm'
              : 'bg-white text-slate-800 border border-slate-200 rounded-bl-sm',
          )}
        >
          {message.role === 'assistant' && message.status === 'pending' ? (
            <PendingIndicator />
          ) : (
            <FormattedContent text={message.content} isUser={isUser} />
          )}
          {message.role === 'assistant' && message.status === 'streaming' && (
            <span className="inline-block w-1.5 h-4 ml-1 bg-slate-400 animate-pulse align-middle" />
          )}
        </div>

        {/* AI の補足情報（引用元・書き換え後クエリ・エラー） */}
        {message.role === 'assistant' && (
          <AssistantAnnotations
            message={message}
            onResultClick={onResultClick}
            onShowSearchResults={onShowSearchResults}
          />
        )}
      </div>
    </div>
  );
});

function Avatar({ role }: { role: 'user' | 'assistant' }) {
  if (role === 'user') {
    return (
      <div className="w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center flex-shrink-0">
        <User className="h-4 w-4 text-slate-600" />
      </div>
    );
  }
  return (
    <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center flex-shrink-0 shadow-sm">
      <Bot className="h-4 w-4 text-white" />
    </div>
  );
}

function PendingIndicator() {
  return (
    <span className="inline-flex items-center gap-2 text-slate-500">
      <Loader2 className="h-3.5 w-3.5 animate-spin" />
      <span className="text-xs">保全記録を検索中…</span>
    </span>
  );
}

interface AssistantAnnotationsProps {
  message: ChatUiMessage;
  onResultClick?: (docId: string) => void;
  onShowSearchResults: () => void;
}

function AssistantAnnotations({
  message,
  onResultClick,
  onShowSearchResults,
}: AssistantAnnotationsProps) {
  if (message.status === 'error') {
    return (
      <Alert variant="destructive" className="py-2">
        <AlertCircle className="h-4 w-4" />
        <AlertDescription className="text-xs">
          {message.errorMessage || '回答生成に失敗しました。'}
        </AlertDescription>
      </Alert>
    );
  }

  const showSources =
    message.sources && message.sources.length > 0 && message.status !== 'pending';
  const showRewritten =
    message.rewrittenQuery &&
    (message.status === 'streaming' || message.status === 'complete');
  const showConfidence = message.status === 'complete' && message.confidence;

  if (!showSources && !showRewritten && !showConfidence) {
    return null;
  }

  return (
    <div className="flex flex-col gap-2 w-full">
      {showRewritten && (
        <div className="text-[11px] text-slate-500 px-2">
          🔎 検索クエリ:{' '}
          <span className="font-medium text-slate-700">{message.rewrittenQuery}</span>
        </div>
      )}

      {showSources && (
        <Card className="p-3 bg-white border-slate-200">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-slate-600">
              📄 引用元（{message.sources!.length}件）
            </span>
            {showConfidence && <ConfidenceBadge confidence={message.confidence!} />}
          </div>
          <ul className="space-y-1.5">
            {message.sources!.map((src, i) => (
              <SourceItem
                key={`${src.doc_id}-${i}`}
                index={i}
                source={src}
                onClick={() => onResultClick?.(src.doc_id)}
              />
            ))}
          </ul>
          {message.status === 'complete' && (
            <div className="mt-3 pt-2 border-t border-slate-100 flex justify-end">
              <Button
                variant="ghost"
                size="sm"
                onClick={onShowSearchResults}
                className="h-7 text-[11px] text-slate-500 hover:text-slate-900"
              >
                全ての検索結果を見る →
              </Button>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}

function SourceItem({
  index,
  source,
  onClick,
}: {
  index: number;
  source: ChatSource;
  onClick: () => void;
}) {
  return (
    <li>
      <button
        type="button"
        onClick={onClick}
        className="w-full flex items-center gap-2 px-2 py-1.5 rounded-md hover:bg-blue-50 border border-transparent hover:border-blue-200 transition-colors text-left group"
      >
        <span className="flex-shrink-0 w-5 h-5 bg-blue-500 group-hover:bg-blue-600 text-white rounded-full flex items-center justify-center text-[10px] font-semibold">
          {index + 1}
        </span>
        <span className="flex-1 text-xs text-slate-700 group-hover:text-blue-700 truncate">
          {source.title}
        </span>
        <span className="flex-shrink-0 px-1.5 py-0.5 bg-emerald-100 text-emerald-800 text-[10px] font-semibold rounded">
          {(source.score * 100).toFixed(0)}%
        </span>
      </button>
    </li>
  );
}

function ConfidenceBadge({ confidence }: { confidence: ChatConfidence }) {
  const label =
    confidence === 'high'
      ? '高信頼度'
      : confidence === 'low'
        ? '低信頼度'
        : confidence === 'unavailable'
          ? '利用不可'
          : '参考情報';
  const color =
    confidence === 'high'
      ? 'bg-emerald-100 text-emerald-800'
      : confidence === 'low'
        ? 'bg-amber-100 text-amber-800'
        : 'bg-slate-100 text-slate-700';

  return (
    <span className={cn('px-2 py-0.5 rounded-full text-[10px] font-medium', color)}>
      {label}
    </span>
  );
}

// ==================== コンテンツフォーマッタ ====================

interface FormattedContentProps {
  text: string;
  isUser: boolean;
}

/**
 * Markdown ライクな軽量フォーマッタ
 *
 * - `**bold**` の強調
 * - `N.` 番号付き見出し / `- ` 箇条書き
 * - 改行を空段落として反映
 *
 * 外部 Markdown ライブラリを入れず、LLM が返す定型フォーマットに最適化した
 * 軽量レンダラとして実装している。
 */
function FormattedContent({ text, isUser }: FormattedContentProps) {
  const blocks = useMemo(() => text.split('\n'), [text]);

  if (isUser) {
    // ユーザー発言は単純に改行だけ尊重すれば十分
    return (
      <div className="whitespace-pre-wrap break-words">{text || '\u200B'}</div>
    );
  }

  return (
    <div className="space-y-1.5 break-words">
      {blocks.map((line, i) => {
        const trimmed = line.trim();
        if (!trimmed) return <div key={i} className="h-1.5" />;

        const sectionMatch = trimmed.match(/^(\d+)\.\s*\*\*(.+?)\*\*$/);
        if (sectionMatch) {
          return (
            <h4
              key={i}
              className="font-bold text-[13px] mt-3 mb-0.5 text-slate-900 border-b border-slate-200 pb-0.5"
            >
              {sectionMatch[1]}. {sectionMatch[2]}
            </h4>
          );
        }

        const numberedMatch = trimmed.match(/^(\d+)\.\s+(.+)/);
        if (numberedMatch) {
          return (
            <div key={i} className="flex gap-2 ml-1">
              <span className="text-slate-500 flex-shrink-0">
                {numberedMatch[1]}.
              </span>
              <span>{renderInline(numberedMatch[2])}</span>
            </div>
          );
        }

        if (trimmed.startsWith('- ') || trimmed.startsWith('・')) {
          const content = trimmed.replace(/^[-・]\s*/, '');
          return (
            <div key={i} className="flex gap-2 ml-1">
              <span className="text-slate-400 flex-shrink-0">•</span>
              <span>{renderInline(content)}</span>
            </div>
          );
        }

        return <p key={i}>{renderInline(trimmed)}</p>;
      })}
    </div>
  );
}

function renderInline(text: string) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i}>{part.slice(2, -2)}</strong>;
    }
    return <span key={i}>{part}</span>;
  });
}

// ==================== 空の状態 ====================

function EmptyState({ onSample }: { onSample: (prompt: string) => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-4 text-center py-8">
      <div className="w-14 h-14 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center shadow-lg">
        <Sparkles className="h-6 w-6 text-white" />
      </div>
      <div>
        <h3 className="font-semibold text-slate-900 mb-1">保全アシスタントへようこそ</h3>
        <p className="text-sm text-slate-600 max-w-md px-4">
          {CHAT_CONFIG.INITIAL_GREETING}
        </p>
      </div>
      <div className="w-full max-w-md space-y-2 mt-2">
        <p className="text-xs font-medium text-slate-500 text-left px-1">
          サンプル質問:
        </p>
        {SAMPLE_PROMPTS.map((prompt) => (
          <button
            key={prompt}
            type="button"
            onClick={() => onSample(prompt)}
            className="w-full text-left text-sm px-3 py-2 rounded-lg border border-slate-200 bg-white hover:border-blue-300 hover:bg-blue-50 hover:text-blue-900 transition-colors"
          >
            {prompt}
          </button>
        ))}
      </div>
    </div>
  );
}
