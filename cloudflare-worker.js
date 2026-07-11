const FROM_EMAIL = 'Datavoy <updates@shiyuantian.co>';
const RESEND_RPS = 2; // Resend free tier: 2 requests per second

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function emailLang(rec) {
  return rec && rec.language ? rec.language : 'zh';
}

function confirmEmail(lang, confirmUrl, nameText) {
  const greeting = nameText
    ? (lang === 'en' ? `<p>Hi ${nameText},</p>` : `<p>Hi ${nameText}，</p>`)
    : (lang === 'en' ? '<p>Hello,</p>' : '<p>你好，</p>');
  const subject = lang === 'en'
    ? 'Please confirm your Datavoy subscription'
    : '请确认订阅 Datavoy 数据更新';
  const html = `
    <div style="max-width:480px;margin:40px auto;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,'PingFang SC','Microsoft YaHei',sans-serif;line-height:1.6;color:#0f172a;">
      <h2 style="color:#0e7490;">Datavoy · 旅数参考</h2>
      ${greeting}
      <p>${lang === 'en' ? 'Thanks for subscribing to data update alerts.' : '感谢你订阅数据更新通知。'}</p>
      <p>${lang === 'en' ? 'Please click the button below to confirm:' : '请点击下方按钮确认订阅：'}</p>
      <p><a href="${confirmUrl}" style="display:inline-block;padding:12px 24px;background:#0e7490;color:#fff;text-decoration:none;border-radius:8px;font-weight:600;">${lang === 'en' ? 'Confirm Subscription' : '确认订阅'}</a></p>
      <p style="font-size:13px;color:#64748b;">${lang === 'en' ? 'If you did not request this, please ignore this email.' : '如果这不是你操作的，请忽略此邮件。'}</p>
    </div>
  `;
  return { subject, html };
}

function notifyEmail(lang, title, message, link, unsubUrl) {
  const buttonText = lang === 'en' ? 'View Details' : '点击查看详情';
  const footerUnsub = lang === 'en' ? 'Unsubscribe' : '退订';
  const footerLine = lang === 'en' ? 'Datavoy · Travel Data Reference' : 'Datavoy · 旅数参考';
  const html = `
    <div style="max-width:480px;margin:40px auto;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,'PingFang SC','Microsoft YaHei',sans-serif;line-height:1.6;color:#0f172a;">
      <h2 style="color:#0e7490;">${footerLine}</h2>
      <p>${message}</p>
      <p><a href="${link}" style="display:inline-block;padding:12px 24px;background:#0e7490;color:#fff;text-decoration:none;border-radius:8px;font-weight:600;">${buttonText}</a></p>
      <p style="font-size:12px;color:#64748b;margin-top:40px;">---<br>${footerLine}<br><a href="${unsubUrl}" style="color:#64748b;">${footerUnsub}</a></p>
    </div>
  `;
  return { subject: title, html };
}

function confirmPage(lang) {
  return lang === 'en'
    ? htmlResponse('Subscription Confirmed', '<h1>Subscription Confirmed ✅</h1><p>You have successfully subscribed to Datavoy data updates.</p><p><a href="/datavoy/">Back to site</a></p>')
    : htmlResponse('订阅成功', '<h1>订阅成功 ✅</h1><p>你已成功订阅 Datavoy 数据更新。</p><p>当文旅部、交通部等数据更新时，我们会邮件通知你。</p><p><a href="/datavoy/">返回网站</a></p>');
}

function unsubscribePage(lang) {
  return lang === 'en'
    ? htmlResponse('Unsubscribed', '<h1>Unsubscribed</h1><p>You will no longer receive Datavoy data update emails.</p><p><a href="/datavoy/">Back to site</a></p>')
    : htmlResponse('已退订', '<h1>已退订</h1><p>你不会再收到 Datavoy 的数据更新邮件。</p><p><a href="/datavoy/">返回网站</a></p>');
}

async function sendEmail(env, to, subject, html, unsubscribeUrl = null, attempt = 1) {
  const payload = { from: FROM_EMAIL, to, subject, html };
  if (unsubscribeUrl) {
    payload.headers = {
      'List-Unsubscribe': `<${unsubscribeUrl}>`,
      'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click',
    };
  }
  const resp = await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${env.RESEND_API_KEY}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
  if (!resp.ok) {
    const text = await resp.text();
    if (resp.status === 429 && attempt < 3) {
      const retryAfter = resp.headers.get('Retry-After');
      const delayMs = retryAfter ? parseInt(retryAfter, 10) * 1000 : 1000;
      await sleep(delayMs);
      return sendEmail(env, to, subject, html, unsubscribeUrl, attempt + 1);
    }
    throw new Error(`Resend ${resp.status}: ${text}`);
  }
  return resp.json();
}

function jsonResponse(obj, status = 200) {
  return new Response(JSON.stringify(obj), { status, headers: { 'Content-Type': 'application/json' } });
}

function htmlResponse(title, body) {
  return new Response(
    `<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>${title}</title><style>body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,"PingFang SC","Microsoft YaHei",sans-serif;max-width:600px;margin:80px auto;padding:24px;text-align:center;line-height:1.6;color:#0f172a}h1{font-size:28px;margin-bottom:12px}a{color:#0e7490}</style></head><body>${body}</body></html>`,
    { headers: { 'Content-Type': 'text/html;charset=utf-8' } }
  );
}

function validateEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const pathname = url.pathname;

    // API: subscribe
    if (pathname === '/api/subscribe' && request.method === 'POST') {
      try {
        const data = await request.json();
        const email = (data.email || '').trim().toLowerCase();
        const first_name = ((data.first_name || '').trim()) || null;
        const last_name = ((data.last_name || '').trim()) || null;
        const company = ((data.company || '').trim()) || null;
        const job_title = ((data.job_title || '').trim()) || null;
        const phone = (data.phone || '').trim() || null;
        const language = (data.language || 'zh').trim().toLowerCase();
        if (!email || !validateEmail(email)) {
          return jsonResponse({ error: '请输入有效的邮箱地址' }, 400);
        }
        const existingRaw = await env.SUBSCRIBERS.get(`email:${email}`);
        if (existingRaw) {
          const existing = JSON.parse(existingRaw);
          if (existing.status === 'confirmed') {
            return jsonResponse({ success: true, message: '你已经订阅过了' });
          }
        }
        const token = crypto.randomUUID();
        const now = Date.now();
        const nameText = first_name || last_name ? `${first_name || ''} ${last_name || ''}`.trim() : null;
        await env.SUBSCRIBERS.put(`email:${email}`, JSON.stringify({
          email, first_name, last_name, company, job_title, phone, language,
          status: 'pending', created: now
        }));
        await env.SUBSCRIBERS.put(`confirm:${token}`, JSON.stringify({ email, created: now }), { expirationTtl: 7 * 86400 });
        const confirmUrl = `https://shiyuantian.co/api/confirm?token=${token}`;
        const { subject, html } = confirmEmail(language, confirmUrl, nameText);
        await sendEmail(env, email, subject, html);
        return jsonResponse({ success: true, message: language === 'en' ? 'Confirmation email sent. Please check your inbox.' : '确认邮件已发送，请查收邮箱。' });
      } catch (e) {
        return jsonResponse({ error: e.message }, 500);
      }
    }

    // API: confirm
    if (pathname === '/api/confirm' && request.method === 'GET') {
      const token = url.searchParams.get('token');
      if (!token) return confirmPage('zh');
      const val = await env.SUBSCRIBERS.get(`confirm:${token}`);
      if (!val) return confirmPage('zh');
      const { email } = JSON.parse(val);
      let lang = 'zh';
      const existingRaw = await env.SUBSCRIBERS.get(`email:${email}`);
      if (existingRaw) {
        const rec = JSON.parse(existingRaw);
        lang = emailLang(rec);
        rec.status = 'confirmed';
        await env.SUBSCRIBERS.put(`email:${email}`, JSON.stringify(rec));
      }
      await env.SUBSCRIBERS.delete(`confirm:${token}`);
      return confirmPage(lang);
    }

    // API: unsubscribe
    if (pathname === '/api/unsubscribe' && request.method === 'GET') {
      const email = (url.searchParams.get('email') || '').trim().toLowerCase();
      let lang = 'zh';
      if (!email || !validateEmail(email)) return unsubscribePage(lang);
      const existingRaw = await env.SUBSCRIBERS.get(`email:${email}`);
      if (existingRaw) {
        const rec = JSON.parse(existingRaw);
        lang = emailLang(rec);
        rec.status = 'unsubscribed';
        await env.SUBSCRIBERS.put(`email:${email}`, JSON.stringify(rec));
      }
      return unsubscribePage(lang);
    }

    // API: subscribers (admin)
    if (pathname === '/api/subscribers' && request.method === 'GET') {
      const auth = request.headers.get('Authorization') || '';
      if (auth !== `Bearer ${env.NOTIFY_SECRET}`) {
        return jsonResponse({ error: 'Unauthorized' }, 401);
      }
      try {
        const list = await env.SUBSCRIBERS.list({ prefix: 'email:' });
        const subscribers = [];
        for (const key of list.keys) {
          const raw = await env.SUBSCRIBERS.get(key.name);
          if (raw) subscribers.push(JSON.parse(raw));
        }
        const confirmed = subscribers.filter(s => s.status === 'confirmed').length;
        const pending = subscribers.filter(s => s.status === 'pending').length;
        const unsubscribed = subscribers.filter(s => s.status === 'unsubscribed').length;
        return jsonResponse({ total: subscribers.length, confirmed, pending, unsubscribed, subscribers });
      } catch (e) {
        return jsonResponse({ error: e.message }, 500);
      }
    }

    // API: notify (admin)
    if (pathname === '/api/notify' && request.method === 'POST') {
      const auth = request.headers.get('Authorization') || '';
      if (auth !== `Bearer ${env.NOTIFY_SECRET}`) {
        return jsonResponse({ error: 'Unauthorized' }, 401);
      }
      try {
        const data = await request.json();
        const { title, message, link, emails, title_en, message_en } = data;
        if (!title || !message || !link) {
          return jsonResponse({ error: 'Missing title/message/link' }, 400);
        }
        const allowedEmails = Array.isArray(emails) && emails.length > 0
          ? new Set(emails.map(e => e.trim().toLowerCase()))
          : null;
        const list = await env.SUBSCRIBERS.list({ prefix: 'email:' });
        let sent = 0, failed = 0;
        const errors = [];
        const delayMs = Math.ceil(1000 / RESEND_RPS) + 100; // ~600ms between sends
        for (const key of list.keys) {
          const rec = JSON.parse(await env.SUBSCRIBERS.get(key.name));
          if (rec.status !== 'confirmed') continue;
          if (allowedEmails && !allowedEmails.has(rec.email.toLowerCase())) continue;
          const lang = emailLang(rec);
          const emailTitle = lang === 'en' && title_en ? title_en : title;
          const emailMessage = lang === 'en' && message_en ? message_en : message;
          const unsubUrl = `https://shiyuantian.co/api/unsubscribe?email=${encodeURIComponent(rec.email)}`;
          const { subject, html } = notifyEmail(lang, emailTitle, emailMessage, link, unsubUrl);
          try {
            await sendEmail(env, rec.email, subject, html, unsubUrl);
            sent++;
          } catch (e) {
            failed++;
            errors.push({ email: rec.email, error: e.message });
          }
          // Resend free tier rate limit: respect ~2 req/sec
          await sleep(delayMs);
        }
        return jsonResponse({ sent, failed, errors });
      } catch (e) {
        return jsonResponse({ error: e.message }, 500);
      }
    }

    // Proxy to GitHub Pages
    const originalHost = url.host;
    const targetHost = 'shiyuantian.github.io';
    let path = pathname;
    const search = url.search;
    if (path === '/' || path === '') {
      return Response.redirect(`${url.protocol}//${originalHost}/datavoy/`, 302);
    }
    if (path === '/datavoy' || path === '/datavoy/') {
      path = '/datavoy/';
    } else if (path.startsWith('/datavoy/')) {
      path = path.slice('/datavoy'.length);
    } else {
      return Response.redirect(`${url.protocol}//${originalHost}/datavoy/`, 302);
    }
    const targetUrl = `${url.protocol}//${targetHost}${path}${search}`;
    const modifiedRequest = new Request(targetUrl, {
      method: request.method,
      headers: { ...Object.fromEntries(request.headers), host: targetHost },
      body: request.body,
    });
    const response = await fetch(modifiedRequest);
    const newHeaders = new Headers(response.headers);
    const location = newHeaders.get('location');
    if (location) {
      newHeaders.set('location', location.replace(`https://${targetHost}`, `https://${originalHost}/datavoy`));
    }
    return new Response(response.body, { status: response.status, statusText: response.statusText, headers: newHeaders });
  },
};
