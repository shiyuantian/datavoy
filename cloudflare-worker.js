const FROM_EMAIL = 'Datavoy <updates@shiyuantian.co>';

async function sendEmail(env, to, subject, html, unsubscribeUrl = null) {
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
          email, first_name, last_name, company, job_title, phone,
          status: 'pending', created: now
        }));
        await env.SUBSCRIBERS.put(`confirm:${token}`, JSON.stringify({ email, created: now }), { expirationTtl: 7 * 86400 });
        const confirmUrl = `https://shiyuantian.co/api/confirm?token=${token}`;
        const greeting = nameText ? `<p>Hi ${nameText}，</p>` : '<p>你好，</p>';
        await sendEmail(env, email, '请确认订阅 Datavoy 数据更新', `
          <div style="max-width:480px;margin:40px auto;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,'PingFang SC','Microsoft YaHei',sans-serif;line-height:1.6;color:#0f172a;">
            <h2 style="color:#0e7490;">Datavoy · 旅数参考</h2>
            ${greeting}
            <p>感谢你订阅数据更新通知。</p>
            <p>请点击下方按钮确认订阅：</p>
            <p><a href="${confirmUrl}" style="display:inline-block;padding:12px 24px;background:#0e7490;color:#fff;text-decoration:none;border-radius:8px;font-weight:600;">确认订阅</a></p>
            <p style="font-size:13px;color:#64748b;">如果这不是你操作的，请忽略此邮件。</p>
            <p style="font-size:12px;color:#94a3b8;">提示：若收件箱未看到这封邮件，请检查「垃圾邮件」或「推广邮件」文件夹。</p>
          </div>
        `);
        return jsonResponse({ success: true, message: '确认邮件已发送，请查收邮箱。若收件箱没有，请检查垃圾邮件/推广邮件夹。' });
      } catch (e) {
        return jsonResponse({ error: e.message }, 500);
      }
    }

    // API: confirm
    if (pathname === '/api/confirm' && request.method === 'GET') {
      const token = url.searchParams.get('token');
      if (!token) return htmlResponse('确认失败', '<h1>链接无效</h1>');
      const val = await env.SUBSCRIBERS.get(`confirm:${token}`);
      if (!val) return htmlResponse('确认失败', '<h1>链接已过期或无效</h1>');
      const { email } = JSON.parse(val);
      const existingRaw = await env.SUBSCRIBERS.get(`email:${email}`);
      if (existingRaw) {
        const rec = JSON.parse(existingRaw);
        rec.status = 'confirmed';
        await env.SUBSCRIBERS.put(`email:${email}`, JSON.stringify(rec));
      }
      await env.SUBSCRIBERS.delete(`confirm:${token}`);
      return htmlResponse('订阅成功', `<h1>订阅成功 ✅</h1><p>你已成功订阅 Datavoy 数据更新。</p><p>当文旅部、交通部等数据更新时，我们会邮件通知你。</p><p><a href="/datavoy/">返回网站</a></p>`);
    }

    // API: unsubscribe
    if (pathname === '/api/unsubscribe' && request.method === 'GET') {
      const email = (url.searchParams.get('email') || '').trim().toLowerCase();
      if (!email || !validateEmail(email)) return htmlResponse('退订失败', '<h1>链接无效</h1>');
      const existingRaw = await env.SUBSCRIBERS.get(`email:${email}`);
      if (existingRaw) {
        const rec = JSON.parse(existingRaw);
        rec.status = 'unsubscribed';
        await env.SUBSCRIBERS.put(`email:${email}`, JSON.stringify(rec));
      }
      return htmlResponse('已退订', `<h1>已退订</h1><p>你不会再收到 Datavoy 的数据更新邮件。</p><p><a href="/datavoy/">返回网站</a></p>`);
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
        const { title, message, link } = data;
        if (!title || !message || !link) {
          return jsonResponse({ error: '缺少 title/message/link' }, 400);
        }
        const list = await env.SUBSCRIBERS.list({ prefix: 'email:' });
        let sent = 0, failed = 0;
        const errors = [];
        for (const key of list.keys) {
          const rec = JSON.parse(await env.SUBSCRIBERS.get(key.name));
          if (rec.status !== 'confirmed') continue;
          const unsubUrl = `https://shiyuantian.co/api/unsubscribe?email=${encodeURIComponent(rec.email)}`;
          try {
            await sendEmail(env, rec.email, title, `
              <div style="max-width:480px;margin:40px auto;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,'PingFang SC','Microsoft YaHei',sans-serif;line-height:1.6;color:#0f172a;">
                <h2 style="color:#0e7490;">Datavoy · 旅数参考</h2>
                <p>${message}</p>
                <p><a href="${link}" style="display:inline-block;padding:12px 24px;background:#0e7490;color:#fff;text-decoration:none;border-radius:8px;font-weight:600;">点击查看详情</a></p>
                <p style="font-size:12px;color:#64748b;margin-top:40px;">---<br>Datavoy · 旅数参考<br><a href="${unsubUrl}" style="color:#64748b;">退订</a></p>
              </div>
            `, unsubUrl);
            sent++;
          } catch (e) {
            failed++;
            errors.push({ email: rec.email, error: e.message });
          }
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
