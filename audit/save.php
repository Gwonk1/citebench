<?php
// citebench misgrounded-grader audit verdict store (isyfert.com/enrich/citebench-audit/save.php).
// Behind the vhost-wide OIDC gate. Append-only JSONL; the latest line per id wins.
// GET  -> {"<id>": {"verdict":"right|wrong|unsure","note":"..","ts":".."}, ...}
// POST {"id":"Q01|N01","verdict":"right|wrong|unsure|clear","note":".."} -> {"ok":true,"ts":..,"count":N}
$file = '/var/lib/syfert/citebench-audit/verdicts.jsonl';
header('Content-Type: application/json');
header('Cache-Control: no-store');
function fold($file) {
    $all = [];
    if (!is_file($file)) return $all;
    foreach (file($file, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) as $line) {
        $r = json_decode($line, true);
        if (!is_array($r) || !isset($r['id'], $r['verdict'])) continue;
        if ($r['verdict'] === 'clear') { unset($all[$r['id']]); continue; }
        $all[$r['id']] = ['verdict' => $r['verdict'], 'note' => $r['note'] ?? '', 'ts' => $r['ts'] ?? ''];
    }
    return $all;
}
if ($_SERVER['REQUEST_METHOD'] === 'GET') {
    $all = fold($file);
    echo $all ? json_encode($all, JSON_UNESCAPED_UNICODE) : '{}';
    exit;
}
if ($_SERVER['REQUEST_METHOD'] !== 'POST') { http_response_code(405); echo '{"ok":false,"error":"POST only"}'; exit; }
$in = json_decode(file_get_contents('php://input'), true);
$allowed = ['right', 'wrong', 'unsure', 'clear'];
if (!is_array($in) || !isset($in['id'], $in['verdict']) || !preg_match('/^[QN]\d{2}$/', (string)$in['id'])
    || !in_array($in['verdict'], $allowed, true)) {
    http_response_code(400); echo '{"ok":false,"error":"bad input"}'; exit;
}
$ts = gmdate('c');
$rec = ['id' => $in['id'], 'verdict' => $in['verdict'],
        'note' => isset($in['note']) ? mb_substr((string)$in['note'], 0, 4000) : '',
        'ts' => $ts, 'user' => $_SERVER['OIDC_CLAIM_email'] ?? ($_SERVER['REMOTE_USER'] ?? '')];
$fp = fopen($file, 'a');
if (!$fp || !flock($fp, LOCK_EX)) { http_response_code(500); echo '{"ok":false,"error":"lock failed"}'; exit; }
fwrite($fp, json_encode($rec, JSON_UNESCAPED_UNICODE) . "\n");
fflush($fp); flock($fp, LOCK_UN); fclose($fp);
echo json_encode(['ok' => true, 'ts' => $ts, 'count' => count(fold($file))]);
